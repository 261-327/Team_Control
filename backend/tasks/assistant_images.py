"""Optional local Diffusers runner. No image service subscriptions or API keys."""

import io

from django.conf import settings

from .assistant_service import AssistantUnavailable

_pipeline = None


def generate_image(prompt):
    global _pipeline
    if not settings.ASSISTANT_IMAGES_ENABLED:
        raise AssistantUnavailable(
            "Генерация изображений выключена. Запустите ./setup-ai.sh --images."
        )
    try:
        import torch
        from diffusers import AutoPipelineForText2Image
    except ImportError as exc:
        raise AssistantUnavailable(
            "Для изображений нужны дополнительные зависимости: ./setup-ai.sh --images."
        ) from exc
    try:
        if _pipeline is None:
            device = (
                "cuda"
                if torch.cuda.is_available()
                else "mps"
                if torch.backends.mps.is_available()
                else "cpu"
            )
            dtype = torch.float32 if device == "cpu" else torch.float16
            _pipeline = AutoPipelineForText2Image.from_pretrained(
                settings.ASSISTANT_IMAGE_MODEL,
                dtype=dtype,
                variant="fp16",
                use_safetensors=True,
                local_files_only=True,
            )
            _pipeline.enable_attention_slicing()
            _pipeline.vae.enable_tiling()
            if device == "cuda":
                _pipeline.enable_model_cpu_offload()
            else:
                _pipeline.to(device)
        image = _pipeline(
            prompt=prompt, guidance_scale=0.0, num_inference_steps=4, height=512, width=512
        ).images[0]
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="PNG", optimize=True)
        return buffer.getvalue()
    except (OSError, RuntimeError, ValueError) as exc:
        # Free GPU/MPS memory on a failed job before trying the next one.
        _pipeline = None
        raise AssistantUnavailable(
            "Не удалось запустить генератор изображений. Проверьте загрузку модели и свободную память."
        ) from exc
