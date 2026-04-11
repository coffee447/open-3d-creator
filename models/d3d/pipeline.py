import os
import torch
import numpy as np
from typing import Any
from PIL import Image
from tqdm import tqdm
from omegaconf import OmegaConf
from huggingface_hub import hf_hub_download
from typing import Union, List, Optional

from models.d3d import sparse as sp
from models.d3d.utils import (
    instantiate_from_config, 
    preprocess_image, 
    sort_block, 
    extract_tokens_and_coords,
    normalize_mesh,
    mesh2index,
)
from models.d3d.dtypes import ImageMode, Mode, Output, SparseDecoderInputs, DenseDecoderInputs, DiffusionInputs, Device
from enum import Enum


class Direct3DS2Pipeline(object):
    def __init__(self, 
                 vae_dense,
                 vae_sparse_512,
                 vae_sparse_1024,
                 dit_dense,
                 dit_sparse_512,
                 dit_sparse_1024,
                 image_encoder_dense,
                 image_encoder_sparse,
                 scheduler_dense,
                 scheduler_sparse_512,
                 scheduler_sparse_1024,
                 refiner,
                 refiner_1024,
                 dtype=torch.float16,
        ):
        self.vae_dense = vae_dense
        self.vae_sparse_512 = vae_sparse_512
        self.vae_sparse_1024 = vae_sparse_1024
        self.dit_dense = dit_dense
        self.dit_sparse_512 = dit_sparse_512
        self.dit_sparse_1024 = dit_sparse_1024
        self.image_encoder_dense = image_encoder_dense
        self.image_encoder_sparse = image_encoder_sparse
        self.scheduler_dense = scheduler_dense
        self.scheduler_sparse_512 = scheduler_sparse_512
        self.scheduler_sparse_1024 = scheduler_sparse_1024
        self.refiner = refiner
        self.refiner_1024 = refiner_1024
        self.dtype = dtype
    
    def to(self, device, mode_from: Mode, mode_to: Mode):
        """
        Move pipeline modules to ``device``. Sparse-1024 and refiner-1024 are moved
        only when ``sdf_resolution == 1024`` (the only case where ``__call__`` runs
        the sparse1024 stage), saving VRAM for 256/512 outputs.
        """
        self.device = torch.device(device)
        cpu = torch.device('cpu')
        d = device
        if mode_from == Mode.initial:
            pass
        elif mode_from == Mode.dense:
            self.vae_dense.to(cpu)
            self.dit_dense.to(cpu)
            self.image_encoder_dense.to(cpu)
            self.refiner.to(cpu)
        elif mode_from == Mode.sparse512:
            self.vae_sparse_512.to(cpu)
            self.dit_sparse_512.to(cpu)
            self.image_encoder_sparse.to(cpu)
            self.refiner.to(cpu)
        elif mode_from == Mode.sparse1024:
            self.vae_sparse_1024.to(cpu)
            self.dit_sparse_1024.to(cpu)
            self.image_encoder_sparse.to(cpu)
            self.refiner_1024.to(cpu)
        else:
            raise NotImplementedError()
        torch.cuda.empty_cache()

        if mode_to == Mode.dense:
            self.vae_dense.to(d)
            self.dit_dense.to(d)
            self.image_encoder_dense.to(d)
            self.refiner.to(d)
        elif mode_to == Mode.sparse512:
            self.vae_sparse_512.to(d)
            self.dit_sparse_512.to(d)
            self.image_encoder_sparse.to(d)
            self.refiner.to(d)
        elif mode_to == Mode.sparse1024:
            self.vae_sparse_1024.to(d)
            self.dit_sparse_1024.to(d)
            self.image_encoder_sparse.to(d)
            self.refiner_1024.to(d)
        else:
            raise NotImplementedError()

    @classmethod
    def from_pretrained(cls, pipeline_path, sdf_resolution, subfolder="direct3d-s2-v-1-1"):
        
        if os.path.isdir(pipeline_path):
            config_path = os.path.join(pipeline_path, subfolder, 'config.yaml')
            model_dense_path = os.path.join(pipeline_path, subfolder, 'model_dense.ckpt')
            model_sparse_512_path = os.path.join(pipeline_path, subfolder, 'model_sparse_512.ckpt')
            model_sparse_1024_path = os.path.join(pipeline_path, subfolder, 'model_sparse_1024.ckpt')
            model_refiner_path = os.path.join(pipeline_path, subfolder, 'model_refiner.ckpt')
            model_refiner_1024_path = os.path.join(pipeline_path, subfolder, 'model_refiner_1024.ckpt')
        else:
            config_path = hf_hub_download(
                repo_id=pipeline_path, 
                subfolder=subfolder, 
                filename="config.yaml", 
                repo_type="model"
            )
            model_dense_path = hf_hub_download(
                repo_id=pipeline_path, 
                subfolder=subfolder,
                filename="model_dense.ckpt", 
                repo_type="model"
            )
            model_sparse_512_path = hf_hub_download(
                repo_id=pipeline_path, 
                subfolder=subfolder,
                filename="model_sparse_512.ckpt", 
                repo_type="model"
            )
            model_sparse_1024_path = hf_hub_download(
                repo_id=pipeline_path, 
                subfolder=subfolder,
                filename="model_sparse_1024.ckpt", 
                repo_type="model"
            )
            model_refiner_path = hf_hub_download(
                repo_id=pipeline_path, 
                subfolder=subfolder,
                filename="model_refiner.ckpt", 
                repo_type="model"
            )
            model_refiner_1024_path = hf_hub_download(
                repo_id=pipeline_path, 
                subfolder=subfolder,
                filename="model_refiner_1024.ckpt", 
                repo_type="model"
            )

        cfg = OmegaConf.load(config_path)
        # load dense vae
        state_dict_dense = torch.load(model_dense_path, map_location=Device.cpu.value, weights_only=True)
        vae_dense = instantiate_from_config(cfg.dense_vae)
        vae_dense.load_state_dict(state_dict_dense["vae"], strict=True)
        vae_dense.eval()
        # load dense dit
        dit_dense = instantiate_from_config(cfg.dense_dit)
        dit_dense.load_state_dict(state_dict_dense["dit"], strict=True)
        dit_dense.eval()
        # load image encoder
        image_encoder_dense = instantiate_from_config(cfg.dense_image_encoder)
        image_encoder_sparse = instantiate_from_config(cfg.sparse_image_encoder)
        # load dense scheduler
        scheduler_dense = instantiate_from_config(cfg.dense_scheduler)
        # load refiner
        state_dict_refiner = torch.load(model_refiner_path, map_location=Device.cpu.value, weights_only=True)
        refiner = instantiate_from_config(cfg.refiner)
        refiner.load_state_dict(state_dict_refiner["refiner"], strict=True)
        refiner.eval()

        # load vae and dit for 1024
        state_dict_sparse_1024 = torch.load(model_sparse_1024_path, map_location=Device.cpu.value, weights_only=True)
        vae_sparse_1024 = instantiate_from_config(cfg.sparse_vae_1024)
        vae_sparse_1024.load_state_dict(state_dict_sparse_1024["vae"], strict=True)
        vae_sparse_1024.eval()
        dit_sparse_1024 = instantiate_from_config(cfg.sparse_dit_1024)
        dit_sparse_1024.load_state_dict(state_dict_sparse_1024["dit"], strict=True)
        dit_sparse_1024.eval()
        # load refiner for 1024
        state_dict_refiner_1024 = torch.load(model_refiner_1024_path, map_location=Device.cpu.value, weights_only=True)
        refiner_1024 = instantiate_from_config(cfg.refiner_1024)
        refiner_1024.load_state_dict(state_dict_refiner_1024["refiner"], strict=True)
        refiner_1024.eval()
        # load sparse scheduler
        scheduler_sparse_1024 = instantiate_from_config(cfg.sparse_scheduler_1024)

        # load vae and dit for 512
        state_dict_sparse_512 = torch.load(model_sparse_512_path, map_location=Device.cpu.value, weights_only=True)
        vae_sparse_512 = instantiate_from_config(cfg.sparse_vae_512)
        vae_sparse_512.load_state_dict(state_dict_sparse_512["vae"], strict=True)
        vae_sparse_512.eval()
        dit_sparse_512 = instantiate_from_config(cfg.sparse_dit_512)
        dit_sparse_512.load_state_dict(state_dict_sparse_512["dit"], strict=True)
        dit_sparse_512.eval()
        # load sparse scheduler
        scheduler_sparse_512 = instantiate_from_config(cfg.sparse_scheduler_512)

        return cls(
            vae_dense=vae_dense,
            vae_sparse_512=vae_sparse_512,
            vae_sparse_1024=vae_sparse_1024,
            dit_dense=dit_dense,
            dit_sparse_512=dit_sparse_512,
            dit_sparse_1024=dit_sparse_1024,
            image_encoder_dense=image_encoder_dense,
            image_encoder_sparse=image_encoder_sparse,
            scheduler_dense=scheduler_dense,
            scheduler_sparse_512=scheduler_sparse_512,
            scheduler_sparse_1024=scheduler_sparse_1024,
            refiner=refiner,
            refiner_1024=refiner_1024,
        )


    def preprocess(self, image):
        if image.mode == ImageMode.rgba.value:
            image = np.array(image)
        else:
            if getattr(self, 'birefnet_model', None) is None:
                from direct3d_s2.utils import BiRefNet
                self.birefnet_model = BiRefNet(self.device)
            image = self.birefnet_model.run(image)
        image = preprocess_image(image)
        return image

    def prepare_image(self, image: Union[str, List[str], Image.Image, List[Image.Image]]):
        if not isinstance(image, list):
            image = [image]
        if isinstance(image[0], str):
            image = [Image.open(img) for img in image]
        image = [self.preprocess(img) for img in image]
        image = torch.stack([img for img in image]).to(self.device)
        return image
    
    def encode_image(self, image: torch.Tensor, conditioner: Any, 
                     do_classifier_free_guidance: bool = True, use_mask: bool = False):
        if use_mask:
            cond = conditioner(image[:, :3], image[:, 3:])
        else:
            cond = conditioner(image[:, :3])

        if isinstance(cond, tuple):
            cond, cond_mask = cond
            cond, cond_coords = extract_tokens_and_coords(cond, cond_mask)
        else:
            cond_mask, cond_coords = None, None

        if do_classifier_free_guidance:
            uncond = torch.zeros_like(cond)
        else:
            uncond = None
        
        if cond_coords is not None:
            cond = sp.SparseTensor(cond, cond_coords.int())
            if uncond is not None:
                uncond = sp.SparseTensor(uncond, cond_coords.int())

        return cond, uncond

    def inference(
            self,
            image,
            vae,
            dit,
            conditioner,
            scheduler,
            num_inference_steps: int = 30, 
            guidance_scale: int = 7.0, 
            generator: Optional[torch.Generator] = None,
            latent_index: torch.Tensor = None,
            mode: Enum = Mode.dense, # 'dense', 'sparse512' or 'sparse1024
            remove_interior: bool = False,
            mc_threshold: float = 0.02):
        
        do_classifier_free_guidance = guidance_scale > 0
        if mode == Mode.dense:
            sparse_conditions = False
        else:
            sparse_conditions = dit.sparse_conditions
        cond, uncond = self.encode_image(image, conditioner, 
                                         do_classifier_free_guidance, sparse_conditions)
        batch_size = cond.shape[0]

        if mode == Mode.dense:
            latent_shape = (batch_size, *dit.latent_shape)
        else:
            latent_shape = (len(latent_index), dit.out_channels)
        latents = torch.randn(latent_shape, dtype=self.dtype, device=self.device, generator=generator)

        scheduler.set_timesteps(num_inference_steps, device=self.device)
        timesteps = scheduler.timesteps

        extra_step_kwargs = {
            "generator": generator
        }

        for i, t in enumerate(tqdm(timesteps, desc=f"{mode} Sampling:")):
            latent_model_input = latents
            timestep_tensor = torch.tensor([t], dtype=latent_model_input.dtype, device=self.device)

            if mode == Mode.dense:
                x_input = latent_model_input
            elif mode in [Mode.sparse512, Mode.sparse1024]:
                x_input = sp.SparseTensor(latent_model_input, latent_index.int())

            diffusion_inputs = DiffusionInputs(x = x_input, 
                                               t = timestep_tensor, 
                                               cond = cond)

            noise_pred_cond = dit(diffusion_inputs)
            if mode != Mode.dense:
                noise_pred_cond = noise_pred_cond.feats

            if do_classifier_free_guidance:
                diffusion_inputs.cond = uncond
                noise_pred_uncond = dit(diffusion_inputs)
                if mode != Mode.dense:
                    noise_pred_uncond = noise_pred_uncond.feats
                noise_pred = noise_pred_uncond + guidance_scale * (noise_pred_cond - noise_pred_uncond)
            else:
                noise_pred = noise_pred_cond
            
            latents = scheduler.step(noise_pred, t, latents, **extra_step_kwargs).prev_sample
        
        latents = 1. / vae.latents_scale * latents + vae.latents_shift
        
        if mode != Mode.dense:
            latents = sp.SparseTensor(latents, latent_index.int())
        if mode == Mode.dense:
            decoder_inputs = DenseDecoderInputs(latents = latents, 
                                                return_index = True)
        else:
            decoder_inputs = SparseDecoderInputs(latents = latents)
            if remove_interior:
                decoder_inputs.return_feat = True
        if mode == Mode.sparse1024:
            decoder_inputs.voxel_resolution = 1024

        outputs = vae.decode_mesh(decoder_inputs)

        if remove_interior:
            del latents, noise_pred, noise_pred_cond, noise_pred_uncond, x_input, cond, uncond
            torch.cuda.empty_cache()
            if mode == Mode.sparse512:
                outputs = self.refiner.run(*outputs, mc_threshold=mc_threshold*2.0)
            elif mode == Mode.sparse1024:
                outputs = self.refiner_1024.run(*outputs, mc_threshold=mc_threshold)

        return outputs
    
    @torch.no_grad()
    def __call__(
        self,
        image: Union[str, List[str], Image.Image, List[Image.Image]] = None,
        sdf_resolution: int = 1024,
        dense_sampler_params: dict = {'num_inference_steps': 50, 'guidance_scale': 7.0},
        sparse_512_sampler_params: dict = {'num_inference_steps': 30, 'guidance_scale': 7.0},
        sparse_1024_sampler_params: dict = {'num_inference_steps': 15, 'guidance_scale': 7.0},
        generator: Optional[torch.Generator] = None,
        remesh: bool = False,
        simplify_ratio: float = 0.95,
        mc_threshold: float = 0.2,
        remove_interior: bool = True):

        image = self.prepare_image(image)
        
        # infence with dense mode
        latent_index = self.inference(image, self.vae_dense, self.dit_dense, self.image_encoder_dense,
                                    self.scheduler_dense, generator=generator, mode=Mode.dense, mc_threshold=0.1, **dense_sampler_params)[0]
        latent_index = sort_block(latent_index, self.dit_sparse_512.selection_block_size)

        # infence with sparse512 mode
        self.to(self.device, Mode.dense, Mode.sparse512)
        mesh = self.inference(image, self.vae_sparse_512, self.dit_sparse_512, 
                                self.image_encoder_sparse, self.scheduler_sparse_512, 
                                generator=generator, mode=Mode.sparse512, 
                                mc_threshold=mc_threshold, latent_index=latent_index, 
                                remove_interior=True, **sparse_512_sampler_params)[0]

        # infence with sparse1024 mode
        if sdf_resolution == 1024:
            self.to(self.device, Mode.sparse512, Mode.sparse1024)
            del latent_index
            mesh = normalize_mesh(mesh)
            latent_index = mesh2index(mesh, size=1024, factor=8)
            latent_index = sort_block(latent_index, self.dit_sparse_1024.selection_block_size)
            print(f"number of latent tokens: {len(latent_index)}")
            mesh = self.inference(image, self.vae_sparse_1024, self.dit_sparse_1024, 
                                self.image_encoder_sparse, self.scheduler_sparse_1024, 
                                generator=generator, mode=Mode.sparse1024, 
                                mc_threshold=mc_threshold, latent_index=latent_index, 
                                remove_interior=remove_interior, **sparse_1024_sampler_params)[0]
            self.to(self.device, Mode.sparse1024, Mode.dense)
        else:
            self.to(self.device, Mode.sparse512, Mode.dense)
            
        if remesh:
            import trimesh
            from models.d3d.utils import postprocess_mesh
            filled_mesh = postprocess_mesh(
                vertices=mesh.vertices,
                faces=mesh.faces,
                simplify=True,
                simplify_ratio=simplify_ratio,
                verbose=True,
            )
            mesh = trimesh.Trimesh(filled_mesh[0], filled_mesh[1])

        return Output(mesh = mesh)
        