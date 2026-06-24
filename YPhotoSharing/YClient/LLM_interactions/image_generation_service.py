import logging
import random
import base64
from io import BytesIO

logger = logging.getLogger(__name__)

class ImageGenerationService:
    """
    Wrapper around an image generation model (e.g., Stable Diffusion / SDXL).
    Provides stubs if the actual models are unavailable.
    """
    
    def __init__(self, endpoint_url: str = None, use_local_diffusion: bool = False, local_diffusion_model: str = "segmind/tiny-sd"):
        self.endpoint_url = endpoint_url
        self.use_local_diffusion = use_local_diffusion
        self.local_diffusion_model = local_diffusion_model
        self.pipe = None
        
        logger.info(f"ImageGenerationService initialized with endpoint: {endpoint_url}, local_diffusion: {use_local_diffusion}, model: {local_diffusion_model}")
        
        if self.use_local_diffusion:
            try:
                import torch
                from diffusers import StableDiffusionPipeline
                logger.info(f"Loading StableDiffusionPipeline locally with model: {self.local_diffusion_model}...")
                device = "cuda" if torch.cuda.is_available() else "cpu"
                if device == "cpu" and torch.backends.mps.is_available():
                    device = "mps"
                self.pipe = StableDiffusionPipeline.from_pretrained(
                    self.local_diffusion_model, 
                    torch_dtype=torch.float16 if device == "cuda" else torch.float32
                )
                self.pipe = self.pipe.to(device)
                logger.info(f"StableDiffusionPipeline loaded on {device}.")
            except Exception as e:
                logger.error(f"Failed to load local diffusion model: {e}")
                self.use_local_diffusion = False

        self.placeholder_images = [
            "https://images.unsplash.com/photo-1500622944204-b135684e99fd?auto=format&fit=crop&w=500&q=60",
            "https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=500&q=60",
            "https://images.unsplash.com/photo-1511367461989-f85a21fda167?auto=format&fit=crop&w=500&q=60",
            "https://images.unsplash.com/photo-1531297484001-80022131f5a1?auto=format&fit=crop&w=500&q=60",
            "https://images.unsplash.com/photo-1469474968028-56623f02e42e?auto=format&fit=crop&w=500&q=60"
        ]

    async def generate_image(self, caption: str, topic: str) -> str:
        """
        Generates an image from a prompt. 
        Returns base64 string or a valid URL/stub if using a placeholder.
        """
        if self.use_local_diffusion and self.pipe:
            logger.debug(f"Locally generating image for topic '{topic}'...")
            try:
                prompt = f"A photo about {topic}, {caption[:100]}"
                # Run sync generation in a way that doesn't fully block if possible, 
                # but for this script we just call it.
                image = self.pipe(prompt, num_inference_steps=20).images[0]
                
                buffered = BytesIO()
                image.save(buffered, format="JPEG")
                img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
                return img_str
            except Exception as e:
                logger.error(f"Local image generation failed: {e}.")
                return None

        if self.endpoint_url:
            pass
            
        logger.debug(f"Returning stub image for topic '{topic}'")
        return random.choice(self.placeholder_images)
