from pathlib import Path


class ModelLoadError(RuntimeError):
    pass


class ScamModel:
    def __init__(self, model, tokenizer, torch, device, scam_index: int, max_tokens: int):
        self.model = model
        self.tokenizer = tokenizer
        self.torch = torch
        self.device = device
        self.scam_index = scam_index
        self.max_tokens = max_tokens

    @classmethod
    def load(cls, model_dir: Path, requested_device: str, scam_label_id: str | None):
        if not model_dir.is_dir():
            raise ModelLoadError(f"Model directory does not exist: {model_dir}")
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as exc:
            raise ModelLoadError("Install backend/requirements-model.txt and the appropriate PyTorch build to enable model inference.") from exc
        try:
            tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
            model = AutoModelForSequenceClassification.from_pretrained(model_dir, local_files_only=True)
        except Exception as exc:
            raise ModelLoadError(f"Could not load the local model/tokenizer: {exc}") from exc
        if model.config.num_labels != 2:
            raise ModelLoadError(f"Expected a two-label classifier; model config has num_labels={model.config.num_labels}.")

        scam_index = cls._get_scam_index(model.config, scam_label_id)
        device = "cuda" if requested_device == "auto" and torch.cuda.is_available() else requested_device
        if device == "auto":
            device = "cpu"
        try:
            model.to(device)
            model.eval()
        except Exception as exc:
            raise ModelLoadError(f"Could not place model on device '{device}': {exc}") from exc
        tokenizer_limit = getattr(tokenizer, "model_max_length", 512)
        if not isinstance(tokenizer_limit, int) or tokenizer_limit > 1_000_000:
            tokenizer_limit = 512
        position_limit = int(getattr(model.config, "max_position_embeddings", tokenizer_limit))
        if getattr(model.config, "model_type", "") == "roberta":
            position_limit -= 2  # RoBERTa reserves positions for its padding offset.
        max_tokens = max(8, min(position_limit, tokenizer_limit, 1024))
        return cls(model, tokenizer, torch, device, scam_index, max_tokens)

    @staticmethod
    def _get_scam_index(config, explicit_index: str | None) -> int:
        if explicit_index is not None:
            try:
                index = int(explicit_index)
            except ValueError as exc:
                raise ModelLoadError("SCAMSHIELD_SCAM_LABEL_ID must be 0 or 1.") from exc
            if index not in (0, 1):
                raise ModelLoadError("SCAMSHIELD_SCAM_LABEL_ID must be 0 or 1.")
            return index
        for label, index in (getattr(config, "label2id", {}) or {}).items():
            if str(label).strip().casefold() in {"scam", "spam", "fraud"}:
                return int(index)
        for index, label in (getattr(config, "id2label", {}) or {}).items():
            if str(label).strip().casefold() in {"scam", "spam", "fraud"}:
                return int(index)
        raise ModelLoadError("Model config must identify the scam class in id2label/label2id, or set SCAMSHIELD_SCAM_LABEL_ID.")

    def predict(self, text: str) -> dict:
        encoded = self.tokenizer(text, truncation=True, max_length=self.max_tokens, return_tensors="pt")
        encoded = {key: value.to(self.device) for key, value in encoded.items()}
        with self.torch.inference_mode():
            logits = self.model(**encoded).logits[0]
            scam_score = float(self.torch.softmax(logits, dim=-1)[self.scam_index].item())
        return {"label": "scam" if scam_score >= 0.5 else "legitimate", "scam_score": scam_score}
