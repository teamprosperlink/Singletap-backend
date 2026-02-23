"""
VRIDDHI MATCHING SYSTEM - MODEL DOWNLOADER
Download and quantize DistilGPT2 to ONNX int8 format

Usage:
    python -m matching.download_model

This script:
1. Downloads DistilGPT2 from HuggingFace
2. Exports to ONNX format
3. Quantizes to int8 (~60MB)
4. Saves tokenizer config

Author: Claude
Date: 2026-02-21
"""

import os
import sys
import shutil
from pathlib import Path

# Model configuration
MODEL_NAME = "distilgpt2"
OUTPUT_DIR = Path(__file__).parent.parent / "models" / "distilgpt2-onnx-int8"


def download_and_quantize():
    """Download DistilGPT2 and convert to quantized ONNX."""
    print(f"[1/5] Creating output directory: {OUTPUT_DIR}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Check if already exists
    model_path = OUTPUT_DIR / "model_quantized.onnx"
    if model_path.exists():
        size_mb = model_path.stat().st_size / (1024 * 1024)
        print(f"[OK] Model already exists: {model_path} ({size_mb:.1f} MB)")
        return True

    try:
        print("[2/5] Installing dependencies...")
        import subprocess
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-q",
            "transformers", "onnx", "onnxruntime", "optimum[onnxruntime]"
        ])

        print(f"[3/5] Downloading {MODEL_NAME} from HuggingFace...")
        from transformers import AutoTokenizer, AutoModelForCausalLM

        tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        model = AutoModelForCausalLM.from_pretrained(MODEL_NAME)

        # Set pad token
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        print("[4/5] Exporting to ONNX and quantizing to int8...")
        from optimum.onnxruntime import ORTModelForCausalLM
        from optimum.onnxruntime.configuration import AutoQuantizationConfig

        # Export to ONNX
        temp_dir = OUTPUT_DIR / "temp_onnx"
        ort_model = ORTModelForCausalLM.from_pretrained(
            MODEL_NAME,
            export=True,
            provider="CPUExecutionProvider"
        )
        ort_model.save_pretrained(temp_dir)

        # Quantize to int8
        print("[4.5/5] Applying int8 quantization...")
        from optimum.onnxruntime import ORTQuantizer

        quantizer = ORTQuantizer.from_pretrained(temp_dir)
        qconfig = AutoQuantizationConfig.avx512_vnni(is_static=False, per_channel=False)

        quantizer.quantize(
            save_dir=OUTPUT_DIR,
            quantization_config=qconfig
        )

        # Copy tokenizer files
        print("[5/5] Saving tokenizer...")
        tokenizer.save_pretrained(OUTPUT_DIR)

        # Rename quantized model
        quantized_file = OUTPUT_DIR / "model_quantized.onnx"
        for f in OUTPUT_DIR.glob("*.onnx"):
            if f.name != "model_quantized.onnx":
                shutil.move(str(f), str(quantized_file))
                break

        # Cleanup temp
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

        # Report size
        if quantized_file.exists():
            size_mb = quantized_file.stat().st_size / (1024 * 1024)
            print(f"\n[SUCCESS] Model saved to: {quantized_file}")
            print(f"[SUCCESS] Model size: {size_mb:.1f} MB")
            return True
        else:
            print("[ERROR] Quantized model not found")
            return False

    except ImportError as e:
        print(f"[ERROR] Missing dependency: {e}")
        print("\nInstall with:")
        print("  pip install transformers onnx onnxruntime optimum[onnxruntime]")
        return False

    except Exception as e:
        print(f"[ERROR] Failed to download/convert model: {e}")
        import traceback
        traceback.print_exc()
        return False


def download_simple():
    """
    Simple download using pre-quantized model from HuggingFace Hub.

    This is faster as it downloads an already quantized model.
    """
    print(f"[1/3] Creating output directory: {OUTPUT_DIR}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    model_path = OUTPUT_DIR / "model_quantized.onnx"
    if model_path.exists():
        size_mb = model_path.stat().st_size / (1024 * 1024)
        print(f"[OK] Model already exists: {model_path} ({size_mb:.1f} MB)")
        return True

    try:
        print("[2/3] Downloading pre-quantized DistilGPT2 ONNX...")
        from huggingface_hub import hf_hub_download, snapshot_download

        # Try to download from optimum-intel or similar repo
        # If not available, fall back to manual conversion
        try:
            snapshot_download(
                repo_id="optimum/distilgpt2-onnx",
                local_dir=OUTPUT_DIR,
                local_dir_use_symlinks=False
            )
            print("[3/3] Model downloaded successfully!")
            return True
        except Exception:
            print("[INFO] Pre-quantized model not found, will convert manually...")
            return download_and_quantize()

    except ImportError as e:
        print(f"[ERROR] Missing dependency: {e}")
        print("\nInstall with:")
        print("  pip install huggingface_hub transformers")
        return False

    except Exception as e:
        print(f"[ERROR] Download failed: {e}")
        return False


def verify_model():
    """Verify the model can be loaded."""
    model_path = OUTPUT_DIR / "model_quantized.onnx"

    if not model_path.exists():
        # Check for any ONNX file
        onnx_files = list(OUTPUT_DIR.glob("*.onnx"))
        if onnx_files:
            model_path = onnx_files[0]
        else:
            print(f"[ERROR] No ONNX model found in {OUTPUT_DIR}")
            return False

    print(f"\n[VERIFY] Testing model load: {model_path}")

    try:
        import onnxruntime as ort

        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        session = ort.InferenceSession(
            str(model_path),
            sess_options,
            providers=['CPUExecutionProvider']
        )

        print(f"[VERIFY] Model loaded successfully!")
        print(f"[VERIFY] Input names: {[i.name for i in session.get_inputs()]}")
        print(f"[VERIFY] Output names: {[o.name for o in session.get_outputs()]}")

        return True

    except Exception as e:
        print(f"[VERIFY] Model load failed: {e}")
        return False


def main():
    """Main entry point."""
    print("=" * 60)
    print("VRIDDHI - DistilGPT2 ONNX int8 Model Downloader")
    print("=" * 60)
    print()

    # Try simple download first
    success = download_simple()

    if success:
        verify_model()
        print("\n" + "=" * 60)
        print("Model ready for use!")
        print("Enable in .env: ENABLE_LLM_MESSAGES=1")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("Model download failed. Messages will use template fallback.")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
