from typing import *
from models.d3d.dtypes import Backends

BACKEND = Backends.flash_attn
DEBUG = False

def __from_env():
    import os
    
    global BACKEND
    global DEBUG
    
    env_attn_backend = os.environ.get('ATTN_BACKEND')
    env_sttn_debug = os.environ.get('ATTN_DEBUG')
    
    if env_attn_backend is not None and env_attn_backend in [Backends.xformers.value,  Backends.flash_attn.value, Backends.sdpa.value, Backends.naive.value]:
        BACKEND = Backends(env_attn_backend)
    if env_sttn_debug is not None:
        DEBUG = env_sttn_debug == '1'

    print(f"[ATTENTION] Using backend: {BACKEND}")
        

__from_env()
    

def set_backend(backend: Literal[Backends.xformers, Backends.flash_attn]):
    global BACKEND
    BACKEND = backend

def set_debug(debug: bool):
    global DEBUG
    DEBUG = debug


from .full_attn import *
from .modules import *
