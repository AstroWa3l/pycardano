import os
import tempfile
import time
import warnings
from typing import Dict, List, Optional, Union

import koios_python as kp
from koios_python import URLs

from pycardano.address import Address
from pycardano.backend.base import (
    ALONZO_COINS_PER_UTXO_WORD,
    ChainContext,
    GenesisParameters,
    ProtocolParameters,
)
from pycardano.exception import TransactionFailedException
from pycardano.hash import SCRIPT_HASH_SIZE, DatumHash, ScriptHash
from pycardano.nativescript import NativeScript
from pycardano.network import Network
from pycardano.plutus import ExecutionUnits, PlutusV1Script, PlutusV2Script
from pycardano.serialization import RawCBOR
from pycardano.transaction import (
    Asset,
    AssetName,
    MultiAsset,
    TransactionInput,
    TransactionOutput,
    UTxO,
    Value,
)
from pycardano.types import JsonDict

__all__ = ["KoiosChainContext"]


class KoiosChainContext(ChainContext):
    """A `Koios API <https://www.koios.rest/>`_ API wrapper for the client code to interact with.

    Args:
        project_id (str): A Koios project ID obtained from https://Koios.rest.
        network (Network): Network to use.
        url (str): Base URL for the Koios API. Defaults Preprod url: https://preprod.koios.rest/api/v0/
    """

    api: kp.URLs()
    #_epoch_info: Namespace
    #_epoch_info: api.get_epoch_info(self=None)
    _epoch: Optional[int] = None
    _genesis_param: Optional[GenesisParameters] = None
    _protocol_param: Optional[ProtocolParameters] = None

    def __init__(
        self,
        network: Optional[Network] = None,
        #base_url: str = ApiUrls.preprod.value,
        url: str = kp.URLs(network='preprod').url
    ):
        if network is not None:
            self._network = network
        else:
            self._network = Network.TESTNET

        self._url = (
            url
            if url
            #else ApiUrls.preprod.value
            #if self.network == Network.TESTNET
            #else ApiUrls.mainnet.value
            else kp.URLs(network='preprod').url
            if self.network == Network.TESTNET
            else kp.URLs(network='mainnet').url
        )
        self.api = kp.URLs(url=self._url)
        #self._epoch_info = self.get.epoch_latest()
        self.current_epoch_param = self.api.get_tip()
        self.current_epoch = self.current_epoch_param[0]["epoch_no"]
        self._epoch_info = self.api.get_epoch_info()[0]
        self._epoch = None
        self._genesis_param = None
        self._protocol_param = None

    def _check_epoch_and_update(self):
        if int(time.time()) >= int(self._epoch_info['end_time']):
            self._epoch_info = self.api.get_epoch_info(self.current_epoch)[0]
            return True
        else:
            return False

    @property
    def network(self) -> Network:
        return self._network

    @property
    def epoch(self) -> int:
        if not self._epoch or self._check_epoch_and_update():
            new_epoch: int = self.api.get_epoch_info(self.current_epoch)['epoch_no']
            self._epoch = new_epoch
        return self._epoch

    @property
    def last_block_slot(self) -> int:
        block = self.api.get_blocks()[0]
        return block['abs_slot']

    @property
    def genesis_param(self) -> GenesisParameters:
        if not self._genesis_param or self._check_epoch_and_update():
            params = vars(self.api.get_genesis())
            self._genesis_param = GenesisParameters(**params)
        return self._genesis_param

    @property
    def protocol_param(self) -> ProtocolParameters:
        if not self._protocol_param or self._check_epoch_and_update():
            params = self.api.get_epoch_params()[0]
            self._protocol_param = ProtocolParameters(
                min_fee_constant=int(params['min_fee_b']),
                min_fee_coefficient=int(params['min_fee_a']),
                max_block_size=int(params['max_block_size']),
                max_tx_size=int(params['max_tx_size']),
                max_block_header_size=int(params['max_bh_size']),
                key_deposit=int(params['key_deposit']),
                pool_deposit=int(params['pool_deposit']),
                pool_influence=float(params['influence']),
                monetary_expansion=float(params['monetary_expand_rate']),
                treasury_expansion=float(params['treasury_growth_rate']),
                decentralization_param=float(params['decentralisation']),
                extra_entropy=params['extra_entropy'],
                protocol_major_version=int(params['protocol_major']),
                protocol_minor_version=int(params['protocol_minor']),
                min_utxo=int(params['min_utxo_value']),
                min_pool_cost=int(params['min_pool_cost']),
                price_mem=float(params['price_mem']),
                price_step=float(params['price_step']),
                max_tx_ex_mem=int(params['max_tx_ex_mem']),
                max_tx_ex_steps=int(params['max_tx_ex_steps']),
                max_block_ex_mem=int(params['max_block_ex_mem']),
                max_block_ex_steps=int(params['max_block_ex_steps']),
                max_val_size=int(params['max_val_size']),
                collateral_percent=int(params['collateral_percent']),
                max_collateral_inputs=int(params['max_collateral_inputs']),
                coins_per_utxo_word= ALONZO_COINS_PER_UTXO_WORD,
                coins_per_utxo_byte=int(params['coins_per_utxo_size']),
                cost_models={
                    #k: v.to_dict() for k, v in params['cost_models'].to_dict().items()
                    #k: v.to_dict() for k, v in params.cost_models.to_dict().items()
                    k: v for k, v in eval(params['cost_models']).items()
                },
            )
        return self._protocol_param
    
    def get_script_cbor(self, script_hash: str):
        '''
        Function to get the cbor of a Plutus Scripts
        '''
        num1 = 0
        num2 = 1000
        script_list = self.api.get_plutus_script_list("0-1000")

        while script_list != []:

            for script in script_list:

                if script['script_hash'] == script_hash:

                    tx_hash = script['creation_tx_hash']
                    info = self.api.get_tx_info(tx_hash)[0]['plutus_contracts']
                    cbor = info[0]['bytecode']
                    return cbor
                    
            num1 += 1000
            num2 += 1000
            string = f'{num1}-{num2}'
            print(string)
            script_list = self.api.get_plutus_script_list(string)

        return False
    

    def _get_script(
        self, script_hash: str
    ) -> Union[PlutusV1Script, PlutusV2Script, NativeScript]:
        '''
        script_type = self.api.script(script_hash).type
        if script_type == "plutusV1":
            return PlutusV1Script(bytes.fromhex(self.api.script_cbor(script_hash).cbor))
        elif script_type == "plutusV2":
            return PlutusV2Script(bytes.fromhex(self.api.script_cbor(script_hash).cbor))
        else:
            script_json: JsonDict = self.api.script_json(  
                script_hash, return_type="json"
            )["json"]
            return NativeScript.from_dict(script_json)
        '''
        # Call function to get the CBOR if is Plutus Script
        cbor = self.get_script_cbor(script_hash)

        if cbor is not False:
            return PlutusV1Script(bytes.fromhex(cbor))
        
        # if it is not a Plutus Script we have to check if is a native script
        else:
            num1 = 0
            num2 = 1000
            script_list = self.api.get_native_script_list("0-1000")

            while script_list != []:
                for script in script_list:
                    if script['script_hash'] == script_hash:
                        script_json: JsonDict = script['script']
                        return NativeScript.from_dict(script_json)
                num1 += 1000
                num2 += 1000
                string = f'{num1}-{num2}'
                script_list = self.api.get_native_script_list(string)
            '''
            Antiguo codigo funcionaba aparentemente
            script_list = self.api.get_native_script_list()
            for script in script_list:
                if script['script_hash'] == script_hash:
                    script_json: JsonDict = script['script']
                    return NativeScript.from_dict(script_json)
            '''

    def utxos(self, address: str) -> List[UTxO]:

        utxos = []

        try:
            results = self.api.get_address_info(address)[0]['utxo_set']
            

            for result in results:
                tx_in = TransactionInput.from_primitive(
                    #[result.tx_hash, result.output_index]
                    [result['tx_hash'], result['tx_index']]
                )
                amount = result['value']
                lovelace_amount = 0
                multi_assets = MultiAsset()
                for item in amount:
                    if int(amount) > 0:
                        lovelace_amount = int(amount)
                    else:
                        # The utxo contains Multi-asset
                        data = bytes.fromhex(item.unit)
                        policy_id = ScriptHash(data[:SCRIPT_HASH_SIZE])
                        asset_name = AssetName(data[SCRIPT_HASH_SIZE:])

                        if policy_id not in multi_assets:
                            multi_assets[policy_id] = Asset()
                        multi_assets[policy_id][asset_name] = int(item.quantity)

                amount = Value(lovelace_amount, multi_assets)

                datum_hash = (
                    #DatumHash.from_primitive(result.data_hash)
                    DatumHash.from_primitive(result['datum_hash'])
                    #if result.data_hash and result.inline_datum is None
                    if result['datum_hash'] and result['inline_datum'] is None
                    else None
                )

                datum = None

                if hasattr(result, "inline_datum") and result.inline_datum is not None:
                    datum = RawCBOR(bytes.fromhex(result.inline_datum))

                script = None

                if (
                    hasattr(result, "reference_script_hash")
                    and result.reference_script_hash
                ):
                    script = self._get_script(result['script_hash'])
                    

                tx_out = TransactionOutput(
                    Address.from_primitive(address),
                    amount=amount,
                    datum_hash=datum_hash,
                    datum=datum,
                    script=script,
                )
                utxos.append(UTxO(tx_in, tx_out))

        except IndexError as index_error:
            print(f'Error. Wrong Address. Utxos {index_error}\n')

        return utxos

    def submit_tx(self, cbor: Union[bytes, str]) -> str:
        """Submit a transaction.

        Args:
            cbor (Union[bytes, str]): The serialized transaction to be submitted.

        Returns:
            str: The transaction hash.

        Raises:
            :class:`TransactionFailedException`: When fails to submit the transaction.
        """
        if isinstance(cbor, str):
            cbor = bytes.fromhex(cbor)
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(cbor)
        try:
            response = self.api.submit_tx(f.name)
        except Exception as error:
            os.remove(f.name)
            raise TransactionFailedException(
                f"Failed to submit transaction. Error code: {error.status_code}. Error message: {error.message}"
            ) from error
        os.remove(f.name)
        return response

    #def evaluate_tx(self, cbor: Union[bytes, str]) -> Dict[str, ExecutionUnits]:
    def evaluate_tx(self, tx: str) -> Dict[str, ExecutionUnits]:
        """Evaluate execution units of a transaction.

        Args:
            cbor (Union[bytes, str]): The serialized transaction to be evaluated.

        Returns:
            Dict[str, ExecutionUnits]: A list of execution units calculated for each of the transaction's redeemers

        Raises:
            :class:`TransactionFailedException`: When fails to evaluate the transaction.
        """
        '''
        if isinstance(cbor, bytes):
            cbor = cbor.hex()
        with tempfile.NamedTemporaryFile(delete=False, mode="w") as f:
            f.write(cbor)
        # Koios doesnt have transaction evaluation
        result = self.api.submit_tx(f.name)
        os.remove(f.name)
        return_val = {}
        if not hasattr(result, "EvaluationResult"):
            raise TransactionFailedException(result)
        else:
            for k in vars(result.EvaluationResult):
                return_val[k] = ExecutionUnits(
                    getattr(result.EvaluationResult, k).memory,
                    getattr(result.EvaluationResult, k).steps,
                )
            return return_val
        '''
        result = self.api.get_script_redeemers(tx)[0]['redeemers']
        memory = result [0]['unit_mem']
        steps= result [0]['unit_steps']
        return ExecutionUnits(memory,steps)