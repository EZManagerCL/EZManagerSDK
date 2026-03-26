import math
import os
import time
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from dotenv import load_dotenv
from eth_account import Account
from eth_utils import keccak
from web3 import Web3
from web3.contract import Contract
from web3._utils.events import get_event_data

try:
    from .utils import (
        LN_1P0001,
        load_abi_map,
        load_addresses,
        normalize_bytes32,
        normalize_tick_bounds,
        price_to_tick,
        sort_tokens,
        to_slippage_bps,
    )
except ImportError:
    from utils import (
        LN_1P0001,
        load_abi_map,
        load_addresses,
        normalize_bytes32,
        normalize_tick_bounds,
        price_to_tick,
        sort_tokens,
        to_slippage_bps,
    )


class EZManagerSDK:
    def __init__(
        self,
        web3: Web3,
        account,
        addresses: Dict[str, str],
        abi: Dict[str, list],
        manager: Contract,
        core: Contract,
        usdc: Contract,
        valuation: Optional[Contract],
    ):
        self.web3 = web3
        self.account = account
        self.addresses = addresses
        self.abi = abi
        self.manager = manager
        self.core = core
        self.usdc = usdc
        self.valuation = valuation
        self.error_selector_map = self._build_error_selector_map()
        self._event_maps = self._build_event_maps()
        self.gas_buffer_bps = self._read_env_int('TX_GAS_BUFFER_BPS', 2000)
        self.gas_buffer_min = self._read_env_int('TX_GAS_BUFFER_MIN', 50000)

    def _read_env_int(self, name: str, fallback: int) -> int:
        raw = os.getenv(name)
        if raw is None or str(raw).strip() == '':
            return int(fallback)
        try:
            return max(0, int(raw))
        except Exception:
            return int(fallback)

    def _build_error_selector_map(self) -> Dict[str, Dict[str, Any]]:
        mapping: Dict[str, Dict[str, Any]] = {}
        for abi_items in self.abi.values():
            if not isinstance(abi_items, list):
                continue
            for item in abi_items:
                if not isinstance(item, dict) or item.get('type') != 'error':
                    continue
                name = item.get('name')
                inputs = item.get('inputs') or []
                types = [i.get('type', '') for i in inputs]
                signature = f"{name}({','.join(types)})"
                selector = '0x' + keccak(text=signature).hex()[:8]
                mapping[selector] = {'signature': signature, 'inputs': inputs}
        return mapping

    def _norm_hex(self, value: Any) -> str:
        if value is None:
            return ''
        if isinstance(value, str):
            s = value.strip().lower()
            return s[2:] if s.startswith('0x') else s
        if isinstance(value, (bytes, bytearray)):
            return bytes(value).hex().lower()
        if hasattr(value, 'hex'):
            s = str(value.hex()).lower()
            return s[2:] if s.startswith('0x') else s
        return str(value).strip().lower().replace('0x', '')

    def _format_tx_hash(self, value: Any) -> str:
        norm = self._norm_hex(value)
        if not norm:
            return ''
        return '0x' + norm

    def _event_topic0(self, event_abi: Dict[str, Any]) -> str:
        inputs = event_abi.get('inputs') or []
        signature_types = [i.get('type', '') for i in inputs]
        signature = f"{event_abi.get('name')}({','.join(signature_types)})"
        return self._norm_hex(self.web3.keccak(text=signature))

    def _build_event_maps(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        out: Dict[str, Dict[str, Dict[str, Any]]] = {}
        for abi_key, abi_items in self.abi.items():
            if not isinstance(abi_items, list):
                continue
            by_name: Dict[str, Dict[str, Any]] = {}
            by_topic: Dict[str, Dict[str, Any]] = {}
            for item in abi_items:
                if not isinstance(item, dict) or item.get('type') != 'event':
                    continue
                name = item.get('name')
                if not name:
                    continue
                by_name[name] = item
                by_topic[self._event_topic0(item)] = item
            out[abi_key] = {'by_name': by_name, 'by_topic': by_topic}
        return out

    def _normalize_read_value(self, value: Any) -> Any:
        if isinstance(value, (bytes, bytearray)):
            return '0x' + bytes(value).hex()
        if isinstance(value, list):
            return [self._normalize_read_value(v) for v in value]
        if isinstance(value, tuple):
            return [self._normalize_read_value(v) for v in value]
        return value

    def _get_core_struct_field_names(self, function_name: str) -> Optional[List[str]]:
        for item in self.abi.get('CL_CORE', []):
            if not isinstance(item, dict):
                continue
            if item.get('type') != 'function' or item.get('name') != function_name:
                continue
            outputs = item.get('outputs') or []
            if not outputs:
                return None
            components = outputs[0].get('components') or []
            if not components:
                return None
            names = [str(c.get('name', f'field_{idx}')) for idx, c in enumerate(components)]
            return names
        return None

    def _struct_to_readable_dict(self, function_name: str, value: Any) -> Any:
        names = self._get_core_struct_field_names(function_name)
        if not names or not isinstance(value, (list, tuple)):
            return self._normalize_read_value(value)
        out: Dict[str, Any] = {}
        for idx, name in enumerate(names):
            if idx >= len(value):
                break
            out[name] = self._normalize_read_value(value[idx])
        return out

    def _struct_array_to_readable_dicts(self, function_name: str, values: Any) -> Any:
        names = self._get_core_struct_field_names(function_name)
        if not names or not isinstance(values, (list, tuple)):
            return self._normalize_read_value(values)
        out: List[Dict[str, Any]] = []
        for row in values:
            if not isinstance(row, (list, tuple)):
                out.append({'value': self._normalize_read_value(row)})
                continue
            item: Dict[str, Any] = {}
            for idx, name in enumerate(names):
                if idx >= len(row):
                    break
                item[name] = self._normalize_read_value(row[idx])
            out.append(item)
        return out

    def _extract_revert_data(self, err: Exception) -> Optional[str]:
        queue: List[Any] = [err, getattr(err, 'data', None)]
        if hasattr(err, 'args'):
            queue.extend(list(err.args))
        while queue:
            cur = queue.pop(0)
            if cur is None:
                continue
            if isinstance(cur, str) and cur.startswith('0x') and len(cur) >= 10:
                return cur
            if isinstance(cur, (list, tuple)):
                queue.extend(cur)
                continue
            if isinstance(cur, dict):
                for key in ('data', 'error', 'result', 'message'):
                    if key in cur:
                        queue.append(cur[key])
        return None

    def decode_custom_error(self, revert_data: Optional[str]) -> Optional[Dict[str, Any]]:
        if not revert_data or not isinstance(revert_data, str) or not revert_data.startswith('0x') or len(revert_data) < 10:
            return None
        selector = revert_data[:10]
        if selector == '0x08c379a0':
            try:
                from eth_abi import decode
                message = decode(['string'], bytes.fromhex(revert_data[10:]))[0]
                return {'selector': selector, 'signature': 'Error(string)', 'args': (message,)}
            except Exception:
                return {'selector': selector, 'signature': 'Error(string)', 'args': None}
        if selector == '0x4e487b71':
            try:
                from eth_abi import decode
                code = decode(['uint256'], bytes.fromhex(revert_data[10:]))[0]
                return {'selector': selector, 'signature': 'Panic(uint256)', 'args': (int(code),)}
            except Exception:
                return {'selector': selector, 'signature': 'Panic(uint256)', 'args': None}
        info = self.error_selector_map.get(selector)
        if not info:
            nested = self._extract_nested_revert_data(revert_data)
            if nested:
                nested_decoded = self.decode_custom_error(nested)
                if nested_decoded:
                    out = dict(nested_decoded)
                    out['wrapped_by_selector'] = selector
                    out['wrapped_revert_data'] = nested
                    return out
            return {'selector': selector, 'signature': None, 'args': None}

        decoded_args = None
        arg_hex = revert_data[10:]
        if arg_hex and len(info.get('inputs', [])) > 0:
            try:
                from eth_abi import decode
                types = [i.get('type', '') for i in info['inputs']]
                decoded_args = decode(types, bytes.fromhex(arg_hex))
            except Exception:
                decoded_args = None
        return {'selector': selector, 'signature': info['signature'], 'args': decoded_args}

    def _extract_nested_revert_data(self, revert_data: Optional[str]) -> Optional[str]:
        if not revert_data or not isinstance(revert_data, str) or not revert_data.startswith('0x') or len(revert_data) < 10:
            return None
        try:
            from eth_abi import decode
            payload_hex = revert_data[10:]
            if not payload_hex:
                return None
            inner = decode(['bytes'], bytes.fromhex(payload_hex))[0]
            if isinstance(inner, (bytes, bytearray)) and len(inner) >= 4:
                inner_hex = '0x' + bytes(inner).hex()
                if inner_hex.lower() != revert_data.lower():
                    return inner_hex
        except Exception:
            return None
        return None

    def decode_receipt_events(
        self,
        receipt,
        abi_key: str,
        event_name: Optional[str] = None,
        address: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        event_map = self._event_maps.get(abi_key)
        if not event_map:
            raise ValueError(f'Unknown ABI key for events: {abi_key}')

        target_event_abi = None
        target_topic0 = None
        if event_name:
            target_event_abi = event_map['by_name'].get(event_name)
            if not target_event_abi:
                raise ValueError(f'Event {event_name} missing in ABI {abi_key}')
            target_topic0 = self._event_topic0(target_event_abi)

        addr_norm = self._norm_hex(address) if address else ''
        logs = getattr(receipt, 'logs', None) or []
        decoded: List[Dict[str, Any]] = []
        for log in logs:
            log_addr = self._norm_hex(log.get('address'))
            if addr_norm and log_addr != addr_norm:
                continue
            topics = log.get('topics', [])
            if not topics:
                continue
            topic0 = self._norm_hex(topics[0])
            event_abi = target_event_abi
            if event_abi is None:
                event_abi = event_map['by_topic'].get(topic0)
                if event_abi is None:
                    continue
            elif topic0 != target_topic0:
                continue

            try:
                parsed = get_event_data(self.web3.codec, event_abi, log)
            except Exception:
                continue

            decoded.append(
                {
                    'event': parsed.get('event'),
                    'args': dict(parsed.get('args', {})),
                    'log': log,
                    'raw': parsed,
                }
            )
        return decoded

    def _raise_with_decoded_error(self, err: Exception) -> None:
        revert_data = self._extract_revert_data(err)
        decoded = self.decode_custom_error(revert_data)
        if not decoded:
            raise err

        if decoded.get('signature'):
            if decoded.get('wrapped_by_selector'):
                msg = (
                    f"Transaction reverted with wrapped custom error selector {decoded['wrapped_by_selector']} "
                    f"inner={decoded['signature']}"
                )
            else:
                msg = f"Transaction reverted with custom error {decoded['signature']}"
        else:
            msg = f"Transaction reverted with unknown custom error selector {decoded.get('selector')}"
        if decoded.get('args') is not None:
            msg += f" args={decoded['args']}"
        if revert_data:
            msg += f" revertData={revert_data}"
        raise RuntimeError(msg) from err

    def _with_gas_buffer(self, estimate: int) -> int:
        est = max(0, int(estimate))
        buffered = est + ((est * int(self.gas_buffer_bps)) // 10000)
        return buffered + int(self.gas_buffer_min)

    def _collect_trace_failures(self, node: Any, path: str = 'root', out: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        if out is None:
            out = []
        if not isinstance(node, dict):
            return out
        if node.get('error'):
            output = node.get('output')
            out.append(
                {
                    'path': path,
                    'error': str(node.get('error')),
                    'output': output if isinstance(output, str) else None,
                    'to': node.get('to'),
                    'from': node.get('from'),
                    'type': node.get('type'),
                }
            )
        calls = node.get('calls') or []
        if isinstance(calls, list):
            for idx, child in enumerate(calls):
                self._collect_trace_failures(child, path=f'{path}.calls[{idx}]', out=out)
        return out

    def _paths_related(self, a: Optional[str], b: Optional[str]) -> bool:
        if not a or not b:
            return False
        return a == b or a.startswith(f'{b}.') or b.startswith(f'{a}.')

    def _trace_failure_summary(self, tx_hash_hex: str) -> Optional[Dict[str, Any]]:
        try:
            response = self.web3.provider.make_request(
                'debug_traceTransaction',
                [tx_hash_hex, {'tracer': 'callTracer'}],
            )
            trace = response.get('result') if isinstance(response, dict) else None
            if not isinstance(trace, dict):
                return None
            failures = self._collect_trace_failures(trace)
            out_of_gas = any('out of gas' in str(f.get('error', '')).lower() for f in failures)
            terminal_failure = failures[-1] if failures else None
            reverse = list(reversed(failures))
            with_output = next(
                (
                    f for f in reverse
                    if isinstance(f.get('output'), str)
                    and f['output'].startswith('0x')
                    and len(f['output']) >= 10
                    and (terminal_failure is None or self._paths_related(f.get('path'), terminal_failure.get('path')))
                ),
                None,
            )
            if with_output is None:
                with_output = next(
                    (
                        f for f in reverse
                        if isinstance(f.get('output'), str) and f['output'].startswith('0x') and len(f['output']) >= 10
                    ),
                    None,
                )
            decoded = self.decode_custom_error(with_output['output']) if with_output else None
            return {
                'failures': failures,
                'out_of_gas': out_of_gas,
                'with_output': with_output,
                'decoded': decoded,
                'terminal_failure': terminal_failure,
            }
        except Exception:
            return None

    def _build_status_zero_error(
        self,
        tx_hash_hex: str,
        tx: Optional[Dict[str, Any]],
        receipt,
        prior_reason: Optional[str] = None,
    ) -> RuntimeError:
        tx_hash_hex = self._format_tx_hash(tx_hash_hex)
        reason = prior_reason
        trace_summary = self._trace_failure_summary(tx_hash_hex)
        out_of_gas = bool(trace_summary and trace_summary.get('out_of_gas'))
        terminal_failure = trace_summary.get('terminal_failure') if trace_summary else None
        with_output = trace_summary.get('with_output') if trace_summary else None
        decoded_related_to_terminal = bool(
            with_output and terminal_failure and self._paths_related(with_output.get('path'), terminal_failure.get('path'))
        )

        if not reason and trace_summary:
            decoded = trace_summary.get('decoded')
            if decoded and decoded.get('signature') and (not out_of_gas or decoded_related_to_terminal):
                reason = decoded['signature']
                if decoded.get('args') is not None:
                    reason += f" args={decoded['args']}"
            elif with_output and (not out_of_gas or decoded_related_to_terminal):
                reason = f"revertData={with_output['output']}"

        gas_used = None
        gas_limit = None
        try:
            gas_used = int(receipt.get('gasUsed')) if receipt and receipt.get('gasUsed') is not None else None
        except Exception:
            gas_used = None
        try:
            tx_onchain = self.web3.eth.get_transaction(tx_hash_hex)
        except Exception:
            tx_onchain = None
        if tx_onchain is not None:
            try:
                gas_limit = int(tx_onchain.get('gas'))
            except Exception:
                gas_limit = None
        if gas_limit is None and tx is not None:
            try:
                gas_limit = int(tx.get('gas')) if tx.get('gas') is not None else None
            except Exception:
                gas_limit = None

        if out_of_gas and (not reason or 'out of gas' not in reason.lower()):
            reason = f'{reason}; execution trace reports out of gas' if reason else 'execution trace reports out of gas'

        parts = [f'Transaction failed on-chain (status=0). tx_hash={tx_hash_hex}']
        if reason:
            parts.append(f'reason={reason}')
        if out_of_gas:
            parts.append('rootCause=out-of-gas')
        if gas_used is not None or gas_limit is not None:
            parts.append(f'gasUsed={gas_used if gas_used is not None else "unknown"} gasLimit={gas_limit if gas_limit is not None else "unknown"}')
        err = RuntimeError(' '.join(parts))
        setattr(err, 'tx_hash', tx_hash_hex)
        setattr(err, 'out_of_gas', out_of_gas)
        setattr(err, 'trace_failures', trace_summary.get('failures') if trace_summary else None)
        return err

    @classmethod
    def from_env(
        cls,
        rpc_url: Optional[str] = None,
        private_key: Optional[str] = None,
        addresses_path: Optional[Path] = None,
        abi_dir: Optional[Path] = None,
    ) -> 'EZManagerSDK':
        load_dotenv()
        rpc = rpc_url or os.getenv('RPC_URL')
        pk = private_key or os.getenv('PRIVATE_KEY')
        if not rpc:
            raise ValueError('RPC_URL is required')
        if not pk:
            raise ValueError('PRIVATE_KEY is required')

        web3 = Web3(Web3.HTTPProvider(rpc))
        account = Account.from_key(pk)

        addresses = load_addresses(addresses_path, web3.eth.chain_id)
        abi = load_abi_map(abi_dir)

        manager = web3.eth.contract(address=Web3.to_checksum_address(addresses['CLManager']), abi=abi['CL_MANAGER'])
        core_addr = manager.functions.CORE().call()
        core = web3.eth.contract(address=Web3.to_checksum_address(core_addr), abi=abi['CL_CORE'])

        usdc_addr = manager.functions.USDC().call()
        usdc = web3.eth.contract(address=Web3.to_checksum_address(usdc_addr), abi=abi['ERC20'])

        valuation = None
        if addresses.get('Valuation'):
            valuation = web3.eth.contract(address=Web3.to_checksum_address(addresses['Valuation']), abi=abi['VALUATION'])

        return cls(web3, account, addresses, abi, manager, core, usdc, valuation)

    @property
    def address(self) -> str:
        return self.account.address

    def _build_tx(self, fn, value: int = 0, gas: Optional[int] = None) -> Dict[str, Any]:
        nonce = self.web3.eth.get_transaction_count(self.address, 'pending')
        tx = fn.build_transaction(
            {
                'from': self.address,
                'nonce': nonce,
                'value': value,
                'chainId': self.web3.eth.chain_id,
            }
        )
        if gas is not None:
            tx['gas'] = int(gas)
        else:
            # build_transaction may auto-fill gas; ignore that and re-estimate so buffer is always applied.
            estimate_tx = dict(tx)
            estimate_tx.pop('gas', None)
            tx['gas'] = self._with_gas_buffer(self.web3.eth.estimate_gas(estimate_tx))
        if 'maxFeePerGas' not in tx and 'gasPrice' not in tx:
            tx['gasPrice'] = self.web3.eth.gas_price
        return tx

    def _send_fn(self, fn, value: int = 0, gas: Optional[int] = None):
        try:
            tx = self._build_tx(fn, value=value, gas=gas)
            signed = self.web3.eth.account.sign_transaction(tx, self.account.key)
            tx_hash = self.web3.eth.send_raw_transaction(signed.raw_transaction)
            tx_hash_hex = self._format_tx_hash(tx_hash)
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            status = int(receipt.get('status', 0))
            if status != 1:
                revert_msg = None
                try:
                    call_tx = {
                        'from': tx.get('from'),
                        'to': tx.get('to'),
                        'data': tx.get('data'),
                        'value': tx.get('value', 0),
                    }
                    self.web3.eth.call(call_tx, block_identifier=receipt.get('blockNumber'))
                except Exception as call_err:
                    revert_data = self._extract_revert_data(call_err)
                    decoded = self.decode_custom_error(revert_data)
                    if decoded and decoded.get('signature'):
                        revert_msg = f"{decoded['signature']}"
                        if decoded.get('args') is not None:
                            revert_msg += f" args={decoded['args']}"
                    elif revert_data:
                        revert_msg = f"revertData={revert_data}"
                    else:
                        revert_msg = str(call_err)
                raise self._build_status_zero_error(
                    tx_hash_hex=tx_hash_hex,
                    tx=tx,
                    receipt=receipt,
                    prior_reason=revert_msg,
                )
            return {'tx_hash': tx_hash_hex, 'receipt': receipt}
        except Exception as err:
            if isinstance(err, RuntimeError):
                raise err
            self._raise_with_decoded_error(err)

    def _call_fn(self, fn, from_address: Optional[str] = None, block_identifier: Any = 'latest'):
        try:
            call_from = from_address or self.address
            return fn.call({'from': Web3.to_checksum_address(call_from)}, block_identifier=block_identifier)
        except Exception as err:
            self._raise_with_decoded_error(err)

    def extract_opened_key_from_receipt(self, receipt) -> Optional[str]:
        events = self.decode_receipt_events(
            receipt=receipt,
            abi_key='CL_MANAGER',
            event_name='PositionOpened',
            address=self.addresses['CLManager'],
        )
        for evt in events:
            key = evt.get('args', {}).get('key')
            if key is None:
                continue
            return normalize_bytes32(key)

        # Fallback: pull indexed key directly from topics using ABI-derived layout.
        event_abi = self._event_maps['CL_MANAGER']['by_name'].get('PositionOpened')
        if not event_abi:
            return None
        topic0 = self._event_topic0(event_abi)
        indexed_inputs = [i for i in (event_abi.get('inputs') or []) if i.get('indexed')]
        key_indexed_idx = next((idx for idx, i in enumerate(indexed_inputs) if i.get('name') == 'key'), -1)
        if key_indexed_idx < 0:
            return None
        topic_index = key_indexed_idx + 1
        manager_addr = self._norm_hex(self.addresses['CLManager'])
        logs = getattr(receipt, 'logs', None) or []
        for log in logs:
            if self._norm_hex(log.get('address')) != manager_addr:
                continue
            topics = log.get('topics', [])
            if len(topics) <= topic_index:
                continue
            if self._norm_hex(topics[0]) != topic0:
                continue
            return normalize_bytes32(topics[topic_index])
        return None

    def call_manager(self, method: str, *args, block_identifier: Any = 'latest'):
        fn = getattr(self.manager.functions, method)
        return self._call_fn(fn(*args), block_identifier=block_identifier)

    def send_manager(self, method: str, *args):
        fn = getattr(self.manager.functions, method)
        return self._send_fn(fn(*args))

    def call_core(self, method: str, *args, block_identifier: Any = 'latest'):
        fn = getattr(self.core.functions, method)
        return self._call_fn(fn(*args), block_identifier=block_identifier)

    def send_core(self, method: str, *args):
        fn = getattr(self.core.functions, method)
        return self._send_fn(fn(*args))

    def usdc_decimals(self) -> int:
        try:
            return int(self.usdc.functions.decimals().call())
        except Exception:
            return 6

    def parse_usdc(self, value: str | float | int) -> int:
        decimals = self.usdc_decimals()
        try:
            parsed = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f'invalid usdc amount: {value}') from exc
        if parsed < 0:
            raise ValueError('usdc amount must be non-negative')
        fractional_digits = max(0, -parsed.as_tuple().exponent)
        if fractional_digits > decimals:
            raise ValueError(f'usdc amount has too many decimal places (max {decimals}): {value}')
        scale = Decimal(10) ** decimals
        return int((parsed * scale).to_integral_value(rounding=ROUND_DOWN))

    def ensure_usdc_allowance(self, spender: str, min_amount: int):
        spender_addr = Web3.to_checksum_address(spender)
        allowance = int(self.usdc.functions.allowance(self.address, spender_addr).call())
        if allowance >= int(min_amount):
            return None
        max_uint = (1 << 256) - 1
        try:
            self._send_fn(self.usdc.functions.approve(spender_addr, max_uint))
        except Exception:
            # Some ERC20s require reset-to-zero before raising allowance.
            self._send_fn(self.usdc.functions.approve(spender_addr, 0))
            self._send_fn(self.usdc.functions.approve(spender_addr, max_uint))

        final_allowance = int(self.usdc.functions.allowance(self.address, spender_addr).call())
        if final_allowance < int(min_amount):
            raise RuntimeError(
                f'USDC allowance insufficient after approve. required={int(min_amount)} actual={final_allowance} spender={spender_addr}'
            )
        return None

    def get_allowed_dex_adapters(self) -> List[str]:
        adapters = self.core.functions.listAllowedDexes().call()
        return [a for a in adapters if int(a, 16) != 0]

    def resolve_dex_adapter(self, dex: str) -> str:
        if dex.startswith('0x') and len(dex) == 42:
            return Web3.to_checksum_address(dex)

        name = dex.lower()
        adapters = self.get_allowed_dex_adapters()

        for addr in adapters:
            adapter = self.web3.eth.contract(address=Web3.to_checksum_address(addr), abi=self.abi['DEX_ADAPTER'])
            is_aer = False
            try:
                is_aer = bool(adapter.functions.isAerodrome().call())
            except Exception:
                is_aer = False

            is_pancake = False
            try:
                is_pancake = bool(adapter.functions.isPancakeSwap().call())
            except Exception:
                is_pancake = False

            if name == 'aerodrome' and is_aer:
                return Web3.to_checksum_address(addr)
            if name in ('pancake', 'pancakeswap') and is_pancake:
                return Web3.to_checksum_address(addr)
            if name == 'uniswap' and (not is_aer and not is_pancake):
                return Web3.to_checksum_address(addr)

        raise ValueError(f'Unable to resolve dex adapter for {dex}')

    def get_pool_address(self, token_a: str, token_b: str, pool_param: int, dex: str) -> str:
        dex_adapter = self.resolve_dex_adapter(dex)
        adapter = self.web3.eth.contract(address=dex_adapter, abi=self.abi['DEX_ADAPTER'])
        factory = adapter.functions.getFactory().call()
        token0, token1 = sort_tokens(Web3.to_checksum_address(token_a), Web3.to_checksum_address(token_b))

        is_aer = False
        try:
            is_aer = bool(adapter.functions.isAerodrome().call())
        except Exception:
            is_aer = False

        if is_aer:
            slip_factory = self.web3.eth.contract(address=factory, abi=self.abi['SLIP_FACTORY'])
            return slip_factory.functions.getPool(token0, token1, int(pool_param)).call()

        uni_factory = self.web3.eth.contract(address=factory, abi=self.abi['UNI_FACTORY'])
        return uni_factory.functions.getPool(token0, token1, int(pool_param)).call()

    def _resolve_pool_context(self, pool_address: str) -> Dict[str, Any]:
        adapters = self.get_allowed_dex_adapters()
        for addr in adapters:
            adapter = self.web3.eth.contract(address=Web3.to_checksum_address(addr), abi=self.abi['DEX_ADAPTER'])
            try:
                token0, token1, fee, tick_spacing = adapter.functions.validateAndGetPoolParams(Web3.to_checksum_address(pool_address)).call()
                is_aer = False
                try:
                    is_aer = bool(adapter.functions.isAerodrome().call())
                except Exception:
                    is_aer = False
                return {
                    'adapter': Web3.to_checksum_address(addr),
                    'token0': Web3.to_checksum_address(token0),
                    'token1': Web3.to_checksum_address(token1),
                    'fee': int(fee),
                    'tick_spacing': abs(int(tick_spacing)),
                    'is_aerodrome': is_aer,
                }
            except Exception:
                continue
        raise ValueError('No allowlisted adapter validated this pool')

    def open_position(self, pool_address: str, tick_lower: int, tick_upper: int, usdc_amount: str | float | int, slippage_bps: int = 50):
        amount_raw = self.parse_usdc(usdc_amount)
        self.ensure_usdc_allowance(self.addresses['CLManager'], amount_raw)
        result = self._send_fn(
            self.manager.functions.openPosition(
                Web3.to_checksum_address(pool_address),
                int(tick_lower),
                int(tick_upper),
                int(amount_raw),
                int(slippage_bps),
            )
        )
        result['position_key'] = self.extract_opened_key_from_receipt(result['receipt'])
        return result

    def open_position_by_pct(
        self,
        pool_address: str,
        usdc_amount: str | float | int,
        lower_pct: Optional[float] = None,
        upper_pct: Optional[float] = None,
        range_pct: Optional[float] = None,
        slippage: float = 0.005,
    ):
        if range_pct is not None and (lower_pct is None and upper_pct is None):
            lower_pct = float(range_pct)
            upper_pct = float(range_pct)
        if lower_pct is None or upper_pct is None:
            raise ValueError('open_position_by_pct requires lower_pct and upper_pct (or range_pct)')
        if not (0 < float(lower_pct) < 1):
            raise ValueError('lower_pct must be in (0,1)')
        if not (0 < float(upper_pct) < 1):
            raise ValueError('upper_pct must be in (0,1)')

        ctx = self._resolve_pool_context(pool_address)
        pool_abi = self.abi['SLIP_POOL'] if ctx['is_aerodrome'] else self.abi['UNI_POOL']
        pool = self.web3.eth.contract(address=Web3.to_checksum_address(pool_address), abi=pool_abi)
        slot0 = pool.functions.slot0().call()
        current_tick = int(slot0[1])
        spacing = max(1, int(ctx['tick_spacing']))

        lower_raw = current_tick + (math.log(1 - float(lower_pct)) / math.log(1.0001))
        upper_raw = current_tick + (math.log(1 + float(upper_pct)) / math.log(1.0001))
        tick_lower, tick_upper = normalize_tick_bounds(lower_raw, upper_raw, spacing)

        return self.open_position(pool_address, tick_lower, tick_upper, usdc_amount, to_slippage_bps(slippage))

    def open_position_by_price(self, pool_address: str, price_lower: float, price_upper: float, usdc_amount: str | float | int, slippage: float = 0.005):
        ctx = self._resolve_pool_context(pool_address)
        erc0 = self.web3.eth.contract(address=ctx['token0'], abi=self.abi['ERC20'])
        erc1 = self.web3.eth.contract(address=ctx['token1'], abi=self.abi['ERC20'])
        dec0 = int(erc0.functions.decimals().call())
        dec1 = int(erc1.functions.decimals().call())
        lo = min(float(price_lower), float(price_upper))
        hi = max(float(price_lower), float(price_upper))
        tick_lower, tick_upper = normalize_tick_bounds(price_to_tick(lo, dec0, dec1), price_to_tick(hi, dec0, dec1), max(1, int(ctx['tick_spacing'])))
        return self.open_position(pool_address, tick_lower, tick_upper, usdc_amount, to_slippage_bps(slippage))

    def add_collateral(self, key: str, usdc_amount: str | float | int, slippage: float = 0.005):
        amount_raw = self.parse_usdc(usdc_amount)
        self.ensure_usdc_allowance(self.addresses['CLManager'], amount_raw)
        return self._send_fn(self.manager.functions.addCollateral(normalize_bytes32(key), amount_raw, to_slippage_bps(slippage)))

    def remove_collateral(self, key: str, usdc_amount: str | float | int, slippage: float = 0.005):
        amount_raw = self.parse_usdc(usdc_amount)
        return self._send_fn(self.manager.functions.removeCollateral(normalize_bytes32(key), amount_raw, to_slippage_bps(slippage)))

    def change_range(self, key: str, tick_lower: int, tick_upper: int, slippage: float = 0.005):
        return self._send_fn(self.manager.functions.changeRange(normalize_bytes32(key), int(tick_lower), int(tick_upper), to_slippage_bps(slippage)))

    def change_range_by_pct(self, key: str, lower_pct: float, upper_pct: float, slippage: float = 0.005):
        if not (0 < float(lower_pct) < 1):
            raise ValueError('lower_pct must be in (0,1)')
        if not (0 < float(upper_pct) < 1):
            raise ValueError('upper_pct must be in (0,1)')

        normalized_key = normalize_bytes32(key)
        details = self.get_position_details_readable(normalized_key)
        position = self.get_position_readable(normalized_key)
        dex = position['dex']
        adapter = self.web3.eth.contract(address=Web3.to_checksum_address(dex), abi=self.abi['DEX_ADAPTER'])
        is_aer = False
        try:
            is_aer = bool(adapter.functions.isAerodrome().call())
        except Exception:
            is_aer = False

        tick_spacing = abs(int(details['tickSpacing']))
        pool_param = tick_spacing if is_aer else int(details['fee'])
        pool_address = self.get_pool_address(details['token0'], details['token1'], pool_param, dex)
        pool_abi = self.abi['SLIP_POOL'] if is_aer else self.abi['UNI_POOL']
        pool = self.web3.eth.contract(address=Web3.to_checksum_address(pool_address), abi=pool_abi)
        slot0 = pool.functions.slot0().call()
        current_tick = int(slot0[1])

        lower_raw = current_tick + (math.log(1 - float(lower_pct)) / LN_1P0001)
        upper_raw = current_tick + (math.log(1 + float(upper_pct)) / LN_1P0001)
        tick_lower, tick_upper = normalize_tick_bounds(lower_raw, upper_raw, max(1, tick_spacing))
        return self.change_range(normalized_key, tick_lower, tick_upper, slippage)

    def change_range_by_price(self, key: str, price_lower: float, price_upper: float, slippage: float = 0.005):
        details = self.get_position_details_readable(normalize_bytes32(key))
        token0 = details['token0']
        token1 = details['token1']
        tick_spacing = abs(int(details['tickSpacing']))

        erc0 = self.web3.eth.contract(address=token0, abi=self.abi['ERC20'])
        erc1 = self.web3.eth.contract(address=token1, abi=self.abi['ERC20'])
        dec0 = int(erc0.functions.decimals().call())
        dec1 = int(erc1.functions.decimals().call())

        lo = min(float(price_lower), float(price_upper))
        hi = max(float(price_lower), float(price_upper))
        tick_lower, tick_upper = normalize_tick_bounds(price_to_tick(lo, dec0, dec1), price_to_tick(hi, dec0, dec1), max(1, tick_spacing))
        return self.change_range(key, tick_lower, tick_upper, slippage)

    def collect_fees_to_usdc(self, keys: Sequence[str], slippage: float = 0.005):
        key_list = [normalize_bytes32(k) for k in keys]
        return self._send_fn(self.manager.functions.collectFeesToUSDC(key_list, to_slippage_bps(slippage)))

    def compound_fees(self, keys: Sequence[str], slippage: float = 0.005):
        key_list = [normalize_bytes32(k) for k in keys]
        return self._send_fn(self.manager.functions.compoundFees(key_list, to_slippage_bps(slippage)))

    def exit_position(self, keys: Sequence[str], slippage: float = 0.005):
        key_list = [normalize_bytes32(k) for k in keys]
        return self._send_fn(self.manager.functions.exitPosition(key_list, to_slippage_bps(slippage)))

    def allow_bot_for_position(self, key: str, allowed: bool = True):
        return self._send_fn(self.manager.functions.allowBotForPosition(normalize_bytes32(key), bool(allowed)))

    def withdraw_dust(self, key: str):
        return self._send_fn(self.manager.functions.withdrawDust(normalize_bytes32(key)))

    def return_nft(self, keys: Sequence[str]):
        key_list = [normalize_bytes32(k) for k in keys]
        return self._send_fn(self.manager.functions.returnNft(key_list))

    def get_user_position_keys(self, user: Optional[str] = None, block_identifier: Any = 'latest'):
        target_user = Web3.to_checksum_address(user or self.address)
        return self._call_fn(
            self.core.functions.listUserPositionKeys(target_user),
            from_address=target_user,
            block_identifier=block_identifier,
        )

    def pending_fees(self, keys: Sequence[str] | str, block_identifier: Any = 'latest') -> List[Dict[str, Any]]:
        key_list = [normalize_bytes32(keys)] if isinstance(keys, str) else [normalize_bytes32(k) for k in keys]
        raw = self._call_fn(
            self.core.functions.pendingFees(key_list),
            block_identifier=block_identifier,
        )
        return self._struct_array_to_readable_dicts('pendingFees', raw)

    def spot_amounts(self, key: str, block_identifier: Any = 'latest') -> Dict[str, Any]:
        raw = self._call_fn(
            self.core.functions.spotAmounts(normalize_bytes32(key)),
            block_identifier=block_identifier,
        )
        return {
            'amt0': self._normalize_read_value(raw[0]),
            'amt1': self._normalize_read_value(raw[1]),
            'owed0': self._normalize_read_value(raw[2]),
            'owed1': self._normalize_read_value(raw[3]),
        }

    def is_pool_allowed(self, pool: str, block_identifier: Any = 'latest') -> bool:
        return bool(
            self._call_fn(
                self.core.functions.isPoolAllowed(Web3.to_checksum_address(pool)),
                block_identifier=block_identifier,
            )
        )

    def is_pool_deprecated(self, pool: str, block_identifier: Any = 'latest') -> bool:
        return bool(
            self._call_fn(
                self.core.functions.isPoolDeprecated(Web3.to_checksum_address(pool)),
                block_identifier=block_identifier,
            )
        )

    def list_allowed_pools(self, block_identifier: Any = 'latest') -> List[str]:
        pools = self._call_fn(self.core.functions.listAllowedPools(), block_identifier=block_identifier)
        return [Web3.to_checksum_address(p) for p in pools or [] if int(p, 16) != 0]

    def position_value_usdc(self, keys: Sequence[str] | str, block_identifier: Any = 'latest') -> List[Dict[str, Any]]:
        key_list = [normalize_bytes32(keys)] if isinstance(keys, str) else [normalize_bytes32(k) for k in keys]
        raw = self._call_fn(
            self.core.functions.positionValueUSDC(key_list),
            block_identifier=block_identifier,
        )
        return self._struct_array_to_readable_dicts('positionValueUSDC', raw)

    def get_user_position_details_readable(
        self,
        user: Optional[str] = None,
        block_identifier: Any = 'latest',
    ) -> List[Dict[str, Any]]:
        keys = self.get_user_position_keys(user=user, block_identifier=block_identifier)
        out: List[Dict[str, Any]] = []
        for key in keys or []:
            normalized_key = normalize_bytes32(key)
            details = self.get_position_details_readable(normalized_key, block_identifier=block_identifier)
            out.append({'key': normalized_key, 'position_details': details})
        return out

    def get_position(self, key: str, block_identifier: Any = 'latest'):
        return self._call_fn(self.core.functions.getPosition(normalize_bytes32(key)), block_identifier=block_identifier)

    def get_position_details(self, key: str, block_identifier: Any = 'latest'):
        return self._call_fn(
            self.core.functions.getPositionDetails(normalize_bytes32(key)),
            block_identifier=block_identifier,
        )

    def get_position_readable(self, key: str, block_identifier: Any = 'latest') -> Dict[str, Any]:
        raw = self.get_position(key, block_identifier=block_identifier)
        return self._struct_to_readable_dict('getPosition', raw)

    def get_position_details_readable(self, key: str, block_identifier: Any = 'latest') -> Dict[str, Any]:
        raw = self.get_position_details(key, block_identifier=block_identifier)
        return self._struct_to_readable_dict('getPositionDetails', raw)

    def wait_for_position(
        self,
        key: str,
        block_identifier: Any = 'latest',
        attempts: int = 6,
        delay_seconds: float = 0.8,
    ) -> Dict[str, Any]:
        last_err: Optional[Exception] = None
        for _ in range(max(1, attempts)):
            try:
                return self.get_position_details_readable(key, block_identifier=block_identifier)
            except Exception as err:
                last_err = err
                time.sleep(max(0.0, delay_seconds))
        if last_err:
            raise last_err
        raise RuntimeError('wait_for_position failed without error')

    def wallet_usdc_balance(self) -> int:
        return int(self.usdc.functions.balanceOf(self.address).call())

    def valuation_usdc(self, dex: str, token: str, amount_raw: int) -> int:
        if self.valuation is None:
            raise RuntimeError('Valuation contract not configured')
        dex_addr = self.resolve_dex_adapter(dex)
        return int(self.valuation.functions.usdcValue(dex_addr, Web3.to_checksum_address(token), int(amount_raw)).call())
