import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(os.getenv("PROJECT_ROOT", "/workspace"))
DIST = ROOT / "dist"
SRC = ROOT / "src"

RUNTIME_DEPENDENCIES = [
    "psycopg[binary]==3.2.1",
]

LAMBDAS = {
    "OrderCreator": SRC / "order_creator_lambda" / "app.py",
    "OrderProcessor": SRC / "order_processor_lambda" / "app.py",
    "NotificationService": SRC / "notification_service_lambda" / "app.py",
}


def package_lambda(name: str, app_path: Path) -> Path:
    DIST.mkdir(parents=True, exist_ok=True)
    output = DIST / f"{name}.zip"

    with tempfile.TemporaryDirectory() as tmp:
        temp_root = Path(tmp)
        subprocess.run(
            ["python3", "-m", "pip", "install", "--no-cache-dir", "-t", str(temp_root), *RUNTIME_DEPENDENCIES],
            check=True,
        )
        shutil.copy2(app_path, temp_root / "app.py")
        shutil.copytree(SRC / "shared", temp_root / "shared")

        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            for file_path in temp_root.rglob("*"):
                if file_path.is_file():
                    archive.write(file_path, file_path.relative_to(temp_root))

    return output


def main() -> None:
    for name, path in LAMBDAS.items():
        artifact = package_lambda(name, path)
        print(f"Packaged {name}: {artifact}")


if __name__ == "__main__":
    main()
