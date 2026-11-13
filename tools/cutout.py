import argparse
import os
import sys
from pathlib import Path

WORKSPACE = Path(os.environ.get("PAPAPAI_WORKSPACE", str(Path(__file__).resolve().parents[1])))
RUNTIME = WORKSPACE / "runtime" / "matting"


def main():
    parser = argparse.ArgumentParser(description="BiRefNet HR and PyMatting transparent cutout")
    parser.add_argument("image", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--runtime", type=Path, default=RUNTIME)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(WORKSPACE.resolve()) or output.suffix.lower() != ".png":
        parser.error("Use a PNG output path inside the workbench directory")
    preview = output.with_name(output.stem + "-深浅底对照.jpg")
    if output.exists() or preview.exists():
        parser.error("Output or preview already exists")
    model = args.runtime / "BiRefNet_HR-matting.onnx"
    packages = args.runtime / "packages"
    if not model.is_file():
        parser.error("BiRefNet HR model or local dependencies are missing")
    if packages.is_dir():
        sys.path.insert(0, str(packages))
    sys.dont_write_bytecode = True
    os.environ["NUMBA_CACHE_DIR"] = str(args.runtime / "numba-cache")
    os.environ.setdefault("NUMBA_NUM_THREADS", "4")

    import numpy as np
    import onnxruntime as ort
    from PIL import Image, ImageOps
    from pymatting import estimate_alpha_cf, estimate_foreground_ml
    from scipy.ndimage import binary_dilation, binary_erosion
    from scipy.special import expit

    with Image.open(args.image) as image:
        source = ImageOps.exif_transpose(image).convert("RGB")
    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    options.enable_cpu_mem_arena = False
    session = ort.InferenceSession(str(model), sess_options=options, providers=["CPUExecutionProvider"])
    entry = session.get_inputs()[0]
    height, width = (v if isinstance(v, int) and v > 0 else 2048 for v in entry.shape[-2:])
    print(f"BiRefNet HR {width}x{height}", flush=True)
    values = np.asarray(source.resize((width, height), Image.Resampling.BICUBIC), dtype=np.float32) / 255
    values = (values - np.array([.485, .456, .406], np.float32)) / np.array([.229, .224, .225], np.float32)
    predicted = np.squeeze(session.run(None, {entry.name: np.ascontiguousarray(values.transpose(2, 0, 1)[None])})[-1])
    if predicted.ndim != 2:
        raise ValueError("Unexpected BiRefNet output")
    if predicted.min() < 0 or predicted.max() > 1:
        predicted = expit(predicted)
    score = np.asarray(Image.fromarray(predicted.astype(np.float32)).resize(source.size, Image.Resampling.BILINEAR))
    pixels = np.asarray(source, dtype=np.float64) / 255
    rough = score > .5
    solid = binary_erosion(rough, iterations=3) & (score > .94)
    possible = binary_dilation(rough, iterations=12) | (score > .03)
    neutral_white = (pixels.min(axis=2) > .972) & (np.ptp(pixels, axis=2) < .024)
    background = (~possible) | (neutral_white & ~solid & (score < .7))
    if not solid.any() or not background.any():
        raise ValueError("The model did not yield both foreground and background")
    trimap = np.full(score.shape, .5)
    trimap[solid] = 1
    trimap[background] = 0
    print("PyMatting alpha and foreground color", flush=True)
    alpha = estimate_alpha_cf(pixels, trimap)
    alpha[solid] = 1
    alpha[background | (alpha < .023)] = 0
    colors = estimate_foreground_ml(pixels, alpha)
    colors[solid] = pixels[solid]
    rgba = np.rint(np.clip(np.dstack((colors, alpha)), 0, 1) * 255).astype(np.uint8)
    rgba[rgba[..., 3] == 0, :3] = 0
    result = Image.fromarray(rgba)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        result.save(stream, format="PNG", optimize=True)
    with Image.open(output) as verified:
        verified.load()
        if verified.mode != "RGBA" or verified.size != source.size or verified.getchannel("A").getextrema() != (0, 255):
            raise ValueError("Invalid RGBA output")
    thumb = result.copy()
    thumb.thumbnail((720, 720), Image.Resampling.LANCZOS)
    panel = Image.new("RGB", (thumb.width * 2, thumb.height))
    for i, color in enumerate(((27, 34, 44), (224, 230, 236))):
        x = i * thumb.width
        panel.paste(color, (x, 0, x + thumb.width, thumb.height))
        panel.paste(thumb, (x, 0), thumb)
    with preview.open("xb") as stream:
        panel.save(stream, format="JPEG", quality=96, subsampling=0)
    print(output, preview, sep="\n")


if __name__ == "__main__":
    main()