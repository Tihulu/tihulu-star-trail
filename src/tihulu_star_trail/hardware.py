from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

VALID_HARDWARE_MODES = {"auto", "cpu", "gpu"}


@dataclass
class HardwareBackend:
    requested: str
    kind: str = "cpu"
    label: str = "CPU"
    available: bool = True
    failure_logged: bool = False

    @property
    def accelerated(self) -> bool:
        return self.kind in {"cuda", "opencl"} and self.available

    def fall_back(self, error: Exception | str, progress: Callable[[str], None] | None = None) -> None:
        if not self.failure_logged and progress is not None:
            progress(f"Hardware acceleration failed ({error}); continuing on CPU")
        self.failure_logged = True
        self.kind = "cpu"
        self.label = "CPU"
        self.available = True


def normalize_hardware_mode(mode: str) -> str:
    normalized = str(mode).strip().lower()
    return normalized if normalized in VALID_HARDWARE_MODES else "auto"


def detect_hardware_backend(
    mode: str = "auto",
    *,
    cv2_module: Any | None = None,
) -> HardwareBackend:
    requested = normalize_hardware_mode(mode)
    if requested == "cpu":
        return HardwareBackend(requested="cpu")
    try:
        cv2 = cv2_module
        if cv2 is None:
            import cv2 as imported_cv2

            cv2 = imported_cv2
        cuda = getattr(cv2, "cuda", None)
        if cuda is not None and int(cuda.getCudaEnabledDeviceCount()) > 0:
            return HardwareBackend(requested=requested, kind="cuda", label="NVIDIA CUDA")
        ocl = getattr(cv2, "ocl", None)
        if ocl is not None and bool(ocl.haveOpenCL()):
            ocl.setUseOpenCL(True)
            if bool(ocl.useOpenCL()):
                return HardwareBackend(requested=requested, kind="opencl", label="OpenCL")
    except Exception:
        pass
    return HardwareBackend(requested=requested, available=requested != "gpu")


def backend_status(backend: HardwareBackend) -> str:
    if backend.accelerated:
        return f"Hardware acceleration: {backend.label}"
    if backend.requested == "gpu" and not backend.available:
        return "Hardware acceleration unavailable; using CPU"
    return "Hardware acceleration: CPU"


def resize_image(
    image: Any,
    size: tuple[int, int],
    backend: HardwareBackend,
    *,
    progress: Callable[[str], None] | None = None,
) -> Any:
    import cv2

    if not backend.accelerated:
        return cv2.resize(image, size, interpolation=cv2.INTER_AREA)
    try:
        if backend.kind == "cuda":
            gpu = cv2.cuda_GpuMat()
            gpu.upload(image)
            resized = cv2.cuda.resize(gpu, size, interpolation=cv2.INTER_AREA).download()
            del gpu
            return resized
        source = cv2.UMat(image)
        resized = cv2.resize(source, size, interpolation=cv2.INTER_AREA).get()
        del source
        return resized
    except Exception as error:
        backend.fall_back(error, progress)
        return cv2.resize(image, size, interpolation=cv2.INTER_AREA)


def maximum_images(
    first: Any,
    second: Any,
    backend: HardwareBackend,
    *,
    progress: Callable[[str], None] | None = None,
) -> Any:
    import cv2
    import numpy as np

    if not backend.accelerated:
        return np.maximum(first, second)
    try:
        if backend.kind == "cuda":
            left = cv2.cuda_GpuMat()
            right = cv2.cuda_GpuMat()
            left.upload(first)
            right.upload(second)
            result = cv2.cuda.max(left, right).download()
            del left, right
            return result
        left = cv2.UMat(first)
        right = cv2.UMat(second)
        result = cv2.max(left, right).get()
        del left, right
        return result
    except Exception as error:
        backend.fall_back(error, progress)
        return np.maximum(first, second)
