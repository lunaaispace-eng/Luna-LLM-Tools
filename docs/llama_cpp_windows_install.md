# Windows llama-cpp-python GGUF Install Guide

This guide is for users who want to run the local `Luna-LLMPrompt` node with GGUF models on Windows.

The difficult part is not the node itself. The difficult part is choosing a `llama-cpp-python` wheel that matches the user's ComfyUI Python and CUDA stack. Installing the wrong wheel can make the local GGUF node fail to import, run on CPU, or crash when a model loads.

This node is tested with JamePeng's `llama-cpp-python` builds because those builds include handler support used by modern Gemma and Qwen GGUF models.

## Automatic Doctor / Installer

This repository includes a helper script:

```text
tools/llama_cpp_windows_doctor.py
```

Default mode is read-only. It inspects the selected ComfyUI Python, checks Python ABI, Torch CUDA, the existing `llama-cpp-python` install, queries JamePeng GitHub releases, and recommends the matching wheel.

Run it from the node folder:

```powershell
$py = 'E:\ComfyUI-Easy-Install\python_embeded\python.exe'
& $py tools\llama_cpp_windows_doctor.py --comfy-root E:\ComfyUI-Easy-Install\ComfyUI
```

Or pass the exact embedded Python:

```powershell
$py = 'E:\ComfyUI-Easy-Install\python_embeded\python.exe'
& $py tools\llama_cpp_windows_doctor.py --python $py
```

To install the recommended wheel, close ComfyUI first, then run:

```powershell
$py = 'E:\ComfyUI-Easy-Install\python_embeded\python.exe'
& $py tools\llama_cpp_windows_doctor.py --python $py --install
```

To save a report:

```powershell
$py = 'E:\ComfyUI-Easy-Install\python_embeded\python.exe'
& $py tools\llama_cpp_windows_doctor.py --python $py --report llama_cpp_report.json
```

The manual steps below explain what the tool is checking.

## What Must Match

Choose the wheel for the ComfyUI Python environment, not for system Python.

The wheel must match:

| Local value | Example | Wheel part |
| --- | --- | --- |
| Python ABI | Python 3.12 | `cp312-cp312` |
| Operating system | Windows 64-bit | `win_amd64` |
| CUDA build family | CUDA 12.8 / 13.0, etc. | `cu128`, `cu130`, etc. |
| llama-cpp-python version | `0.4.7` (0.3.48+ for MTP, 0.4.x for Gemma 4 drafters, 0.4.7 for llama.cpp 1.0 features such as the MoE cache CPU share) | `llama_cpp_python-0.4.7...whl` |

Use the CUDA version reported by PyTorch inside ComfyUI as the main CUDA selector. The CUDA version shown by `nvidia-smi` is the driver runtime capability; it does not always equal the PyTorch wheel CUDA build.

## Step 1: Find ComfyUI Python

Portable ComfyUI builds often use an embedded Python such as:

```powershell
E:\ComfyUI-Easy-Install\python_embeded\python.exe
```

Official portable ComfyUI often uses:

```powershell
ComfyUI_windows_portable\python_embeded\python.exe
```

Set a variable for the rest of the commands:

```powershell
$py = 'E:\ComfyUI-Easy-Install\python_embeded\python.exe'
```

Change the path if your ComfyUI install is somewhere else.

## Step 2: Inspect Python

```powershell
& $py -c "import sys, platform; print(sys.version); print(sys.executable); print(platform.platform())"
```

Map Python version to wheel ABI:

| Python version | Wheel ABI |
| --- | --- |
| 3.10.x | `cp310-cp310` |
| 3.11.x | `cp311-cp311` |
| 3.12.x | `cp312-cp312` |
| 3.13.x | `cp313-cp313` |

Example:

```text
Python 3.12.x -> cp312-cp312
```

## Step 3: Inspect Torch and CUDA

```powershell
& $py -c "import torch; print('torch', torch.__version__); print('torch_cuda', torch.version.cuda); print('cuda_available', torch.cuda.is_available()); print('device', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none')"
```

Examples:

| Torch output | Wheel CUDA selector |
| --- | --- |
| `2.8.x+cu128` / `torch.version.cuda = 12.8` | `cu128` |
| `2.9.x+cu130` / `torch.version.cuda = 13.0` | `cu130` |

Also check the NVIDIA driver:

```powershell
nvidia-smi
```

The driver must be new enough for the CUDA family you are trying to use.

## Step 4: Inspect Existing llama-cpp-python

```powershell
& $py -m pip show llama-cpp-python
```

If it is already installed, inspect the wheel source:

```powershell
$site = (& $py -c "import site; print(site.getsitepackages()[0])")
Get-ChildItem $site -Directory -Filter 'llama_cpp_python*.dist-info'
```

Then read `direct_url.json` if it exists:

```powershell
Get-Content "$site\llama_cpp_python-0.3.40.dist-info\direct_url.json"
```

The folder version may differ from `0.3.40`; use the folder you actually have.

## Step 5: Choose the JamePeng Wheel

Open the JamePeng releases page:

```text
https://github.com/JamePeng/llama-cpp-python/releases
```

Pick a release that matches your CUDA family and Windows.

Wheel filename pattern:

```text
llama_cpp_python-<version>+<cuda>-<python_abi>-<python_abi>-win_amd64.whl
```

Example for:

- Python 3.12
- Torch CUDA 13.0
- Windows 64-bit
- llama-cpp-python 0.4.7

The matching wheel is:

```text
llama_cpp_python-0.4.7+cu130-cp312-cp312-win_amd64.whl
```

Example URL:

```text
https://github.com/JamePeng/llama-cpp-python/releases/download/v0.4.7-cu130-win-20261113/llama_cpp_python-0.4.7+cu130-cp312-cp312-win_amd64.whl
```

Installed on `E:\ComfyUI-Easy-Install` on 2026-11-15 (was 0.4.2+cu130). JamePeng 0.4.7 tracks llama.cpp v1.0.0 without its two
API-pruning commits. The previous wheel, to roll back:
`https://github.com/JamePeng/llama-cpp-python/releases/download/v0.4.2-cu130-win-20261003/llama_cpp_python-0.4.2+cu130-cp312-cp312-win_amd64.whl`

Do not install a `cp311` wheel into Python 3.12. Do not install a `cu128` wheel just because another user used it. Match your own ComfyUI Python and Torch CUDA.

## Step 6: Install the Wheel

Close ComfyUI first.

```powershell
$py = 'E:\ComfyUI-Easy-Install\python_embeded\python.exe'
$wheel = 'https://github.com/JamePeng/llama-cpp-python/releases/download/v0.4.7-cu130-win-20261113/llama_cpp_python-0.4.7+cu130-cp312-cp312-win_amd64.whl'

& $py -m pip uninstall -y llama-cpp-python
& $py -m pip install --no-cache-dir --force-reinstall --no-deps $wheel
```

Keep `--no-deps`. ComfyUI already has a carefully matched Python stack. Letting pip replace dependencies can break Torch, NumPy, or other custom nodes.

## Step 7: Verify Import

```powershell
& $py -c "import llama_cpp, llama_cpp.llama_cpp as lc; print('llama_cpp', getattr(llama_cpp, '__version__', 'unknown')); print('lib', getattr(lc._lib, '_name', 'unknown'))"
```

A healthy install prints the version and a `llama.dll` path from the ComfyUI Python `site-packages`.

## Step 8: Verify the CUDA Backend Loads

Since 0.4.x the wheel loads its backends (`ggml-cuda.dll`, `ggml-cpu-*.dll`) at run time from `llama_cpp\lib`.
`ggml-cuda.dll` needs the CUDA runtime DLLs that ship in `torch\lib`, so import torch first, as ComfyUI does:

```powershell
& $py -c "import torch, os, llama_cpp, llama_cpp._ggml as g; d=os.path.join(os.path.dirname(llama_cpp.__file__),'lib'); g.ggml_backend_load_all_from_path(d.encode()); [print(g.ggml_backend_dev_name(g.ggml_backend_dev_get(i)), g.ggml_backend_dev_description(g.ggml_backend_dev_get(i))) for i in range(g.ggml_backend_dev_count())]"
```

A healthy CUDA install lists `CUDA0` with the GPU name, then `CPU`. Without `import torch` only `CPU` is listed, because
`ggml-cuda.dll` cannot find the CUDA runtime; that is not a broken install (TESTED 2026-11-15, 0.4.7+cu130, RTX 4090).
`llama_supports_gpu_offload()` is not a CUDA check: it also returns True when only the RPC backend is loaded.

## Step 9: Optional GGUF Smoke Test

Put a small GGUF model in `ComfyUI\models\LLM`, then run:

```powershell
$model = 'E:\ComfyUI-Easy-Install\ComfyUI\models\LLM\your-model.gguf'

& $py -c "from llama_cpp import Llama; import sys; model=sys.argv[1]; llm=Llama(model_path=model, n_gpu_layers=-1, n_ctx=512, verbose=True); print(llm('Say OK', max_tokens=8)['choices'][0]['text'])" $model
```

If the wheel is wrong, this is where failures usually become obvious.

## MoE Models: Experts in RAM and the Expert Cache

0.4.7+ only. Luna-LLMPrompt's gear panel › "MoE models" has three settings, off by default:

| Setting | Meaning |
| --- | --- |
| `moe_cpu_layers` | 0 = all on the GPU, -1 = all experts in RAM, N = the experts of the first N layers in RAM |
| `moe_cache_mib` | GPU cache for the most used experts; only with experts in RAM |
| `moe_cache_cpu_share` | share of cache misses the CPU computes instead of uploading them, once the cache is full |

They matter only for MoE models (names with `A3B`, `A4B`). Dense models ignore them. To see which of your models
are MoE (and which have MTP layers), read their headers: `& $py tools\gguf_inventory.py <your GGUF folder>`. If the model fits in VRAM, leave
them off: all on the GPU is fastest. Use them when a video model needs the VRAM.

Measured with llama.cpp's `scripts/moe-cache-tune.py` (v1.0.0, b12359) on Qwen3.6-35B-A3B Q4_K_M (18.6 GB of experts),
RTX 4090, Ryzen 9 7950X3D, 8k context, default (mmap) loading, 2026-11-15. Predicted tok/s with a warm cache:

| Cache MiB | share 0 | share 0.8 | share 0.95 |
| --- | --- | --- | --- |
| 896 | 42.5 | 61.6 | 70.9 |
| 1856 | 54.3 | 71.9 | 79.5 |
| 3712 | 73.6 | 86.0 | 90.9 |
| 5568 | 87.7 | 95.4 | 98.4 |
| 9280 | 105.7 | 106.5 | 108.0 |
| all experts on the GPU | 118.6 | | |

On this PC the CPU share helps (the tool measured uploads at 19.8 GiB/s, the CPU at 71.7 GiB/s): use `-1`, a cache of
what VRAM allows, share `0.95`. A small cache with share 0 is slow. Another PC may differ; the script tunes it there.
Use this pack's copy, `tools\moe_cache_tune.py`: the original stops each server with SIGINT, which Python cannot
send on Windows, and the copy has the Windows change. It drives `llama-server.exe`, which the wheel does not ship;
take it from the llama.cpp release that matches the wheel (for 0.4.7: `llama-b12359-bin-win-cuda-13.5-x64.zip` and
`cudart-llama-bin-win-cuda-13.5-x64.zip`). Pass your own `-m`, `-c`, `-t` and load flags, plus `-cmoe`:

```powershell
& $py tools\moe_cache_tune.py --markdown --out .work\moe-tune -- <path>\llama-server.exe -m <model.gguf> -cmoe -ngl 99 -c 8192 -fa on -t 16
```

Six runs of about two minutes each. The last table is the prediction; the tool's recommendation is under it.

## Common Problems

### `DLL load failed`

Most often caused by a wheel that does not match the Python ABI or by missing runtime DLLs. Recheck Python version and the wheel filename.

### `No module named llama_cpp`

The wheel was installed into the wrong Python. Use ComfyUI's embedded `python.exe`, not system Python.

### It imports, but local GGUF generation fails

Check that the model file is a real `.gguf`, that it is under `ComfyUI\models\LLM`, and that any matching vision projector file is in the same folder when using multimodal models.

### It runs on CPU or is extremely slow

Check the wheel CUDA selector, verify `ggml-cuda.dll` exists, and test with `n_gpu_layers=-1`.

### pip tries to replace Torch or NumPy

Cancel and reinstall with:

```powershell
& $py -m pip install --no-cache-dir --force-reinstall --no-deps <wheel-url>
```

## Future Installer / Doctor Tool

The included `tools/llama_cpp_windows_doctor.py` follows this model: doctor first, installer second.

It should:

1. Ask for or auto-detect the ComfyUI root.
2. Locate the embedded `python.exe`.
3. Detect Python ABI with `sys.version_info`.
4. Detect Torch version, `torch.version.cuda`, CUDA availability, and GPU name.
5. Run `nvidia-smi` when available and record driver/runtime capability.
6. Inspect the existing `llama-cpp-python` install and `direct_url.json`.
7. Query JamePeng GitHub releases.
8. Select a wheel matching `cpXXX`, `cuXXX`, and `win_amd64`.
9. Show the selected wheel and ask before changing the install.
10. Install with `pip install --force-reinstall --no-deps`.
11. Verify import, DLL path, CUDA DLL presence, and optionally run a GGUF smoke test.
12. Write a report with the detected state, selected wheel, install result, and next action.

The tool should never assume the system drive, never use system Python, and never upgrade unrelated packages unless the user explicitly asks for that.
