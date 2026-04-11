from .. import BACKEND
from models.d3d.dtypes import SpconvAlgo, SparseBackends


SPCONV_ALGO = SpconvAlgo.auto    # 'auto', 'implicit_gemm', 'native'

def __from_env():
    import os
        
    global SPCONV_ALGO
    env_spconv_algo = os.environ.get('SPCONV_ALGO')
    if env_spconv_algo is not None and env_spconv_algo in [SpconvAlgo.auto.value, SpconvAlgo.implicit_gemm.value, SpconvAlgo.native.value]:
        SPCONV_ALGO = SpconvAlgo(env_spconv_algo)
    print(f"[SPARSE][CONV] spconv algo: {SPCONV_ALGO}")
        

__from_env()

if BACKEND == SparseBackends.torchsparse:
    from .conv_torchsparse import *
elif BACKEND == SparseBackends.spconv:
    from .conv_spconv import *
