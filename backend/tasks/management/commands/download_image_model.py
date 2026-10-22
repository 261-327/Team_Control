"""Download open model weights explicitly, never during a user's request."""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Download SDXL-Turbo for local educational image generation (no API key)."

    def add_arguments(self, parser):
        parser.add_argument("--directory", default="/models/sdxl-turbo")

    def handle(self, *args, **options):
        from huggingface_hub import snapshot_download

        snapshot_download(
            "stabilityai/sdxl-turbo",
            local_dir=options["directory"],
            allow_patterns=[
                "model_index.json",
                "*/config.json",
                "*/scheduler_config.json",
                "*/tokenizer_config.json",
                "*/special_tokens_map.json",
                "*/vocab.json",
                "*/merges.txt",
                "*/model.fp16.safetensors",
                "*/diffusion_pytorch_model.fp16.safetensors",
            ],
        )
        self.stdout.write(self.style.SUCCESS("Local image model downloaded."))
