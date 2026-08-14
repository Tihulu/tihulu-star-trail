from types import SimpleNamespace

from tihulu_star_trail.hardware import (
    HardwareBackend,
    backend_status,
    detect_hardware_backend,
    normalize_hardware_mode,
)


class FakeCuda:
    def __init__(self, devices: int) -> None:
        self.devices = devices

    def getCudaEnabledDeviceCount(self) -> int:
        return self.devices


class FakeOcl:
    def __init__(self, available: bool) -> None:
        self.available = available
        self.enabled = False

    def haveOpenCL(self) -> bool:
        return self.available

    def setUseOpenCL(self, enabled: bool) -> None:
        self.enabled = enabled

    def useOpenCL(self) -> bool:
        return self.enabled and self.available


def test_hardware_modes_and_cpu_selection() -> None:
    assert normalize_hardware_mode("AUTO") == "auto"
    assert normalize_hardware_mode("unknown") == "auto"
    backend = detect_hardware_backend("cpu", cv2_module=object())
    assert backend.kind == "cpu"
    assert backend_status(backend) == "Hardware acceleration: CPU"


def test_auto_prefers_cuda_then_opencl() -> None:
    cuda_backend = detect_hardware_backend(
        "auto", cv2_module=SimpleNamespace(cuda=FakeCuda(1), ocl=FakeOcl(True))
    )
    opencl_backend = detect_hardware_backend(
        "auto", cv2_module=SimpleNamespace(cuda=FakeCuda(0), ocl=FakeOcl(True))
    )

    assert cuda_backend.kind == "cuda"
    assert opencl_backend.kind == "opencl"


def test_gpu_unavailable_and_runtime_failure_fall_back_to_cpu() -> None:
    backend = detect_hardware_backend(
        "gpu", cv2_module=SimpleNamespace(cuda=FakeCuda(0), ocl=FakeOcl(False))
    )
    assert not backend.available
    assert "unavailable" in backend_status(backend)

    messages: list[str] = []
    active = HardwareBackend(requested="gpu", kind="cuda", label="NVIDIA CUDA")
    active.fall_back(RuntimeError("driver stopped"), messages.append)
    active.fall_back(RuntimeError("again"), messages.append)
    assert active.kind == "cpu"
    assert len(messages) == 1
