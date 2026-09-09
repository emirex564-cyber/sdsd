import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path

URL = "https://github.com/emirex564-cyber/sdsd/raw/refs/heads/main/Vostro3520_Tahoe_POC_EFI.zip"
DRIVE = "S:"
WORK = Path(os.environ.get("TEMP", ".")) / "Vostro3520_Tahoe_POC"
ZIP_PATH = WORK / "Vostro3520_Tahoe_POC_EFI.zip"
USER_HOME = Path(os.environ.get("USERPROFILE", str(Path.home())))
DOWNLOADS_ZIP = USER_HOME / "Downloads" / "Vostro3520_Tahoe_POC_EFI.zip"
DOWNLOADS_ZIP_TR = USER_HOME / "İndirilenler" / "Vostro3520_Tahoe_POC_EFI.zip"
EXTRACTED = WORK / "extracted"
BACKUP = Path("C:/Vostro_EFI_Backups") / datetime.now().strftime("%Y%m%d_%H%M%S")


def fail(message):
    print(f"\nHATA: {message}")
    input("Kapatmak için Enter'a basın...")
    sys.exit(1)


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def run(command, check=True):
    print(">", " ".join(command))
    return subprocess.run(command, text=True, capture_output=True, check=check)


def relaunch_as_admin():
    params = " ".join(f'"{x}"' for x in sys.argv)
    result = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, params, None, 1
    )
    if result <= 32:
        fail("Yönetici izni alınamadı.")
    sys.exit(0)


def main():
    if os.name != "nt":
        fail("Bu script yalnızca Windows'ta çalışır.")
    if not is_admin():
        print("Yönetici izni isteniyor...")
        relaunch_as_admin()

    print("UYARI: Bu işlem Windows Boot Manager dosyasını silmez.")
    print("Mevcut EFI klasörü C:\\Vostro_EFI_Backups içine yedeklenecek.")
    print("Ancak açılış yolu OpenCore olarak değiştirilecek.")
    answer = input("Devam etmek için EVET yaz: ").strip().upper()
    if answer != "EVET":
        print("İptal edildi.")
        return

    WORK.mkdir(parents=True, exist_ok=True)
    if EXTRACTED.exists():
        shutil.rmtree(EXTRACTED)
    EXTRACTED.mkdir(parents=True)

    local_zip = next((p for p in (DOWNLOADS_ZIP, DOWNLOADS_ZIP_TR) if p.is_file()), None)
    if local_zip is not None:
        print(f"Downloads klasöründeki mevcut ZIP kullanılıyor: {local_zip}")
        shutil.copy2(local_zip, ZIP_PATH)
    else:
        print("Downloads klasöründe ZIP bulunamadı; internetten indiriliyor...")
        try:
            urllib.request.urlretrieve(URL, ZIP_PATH)
        except Exception as exc:
            fail(f"ZIP indirilemedi: {exc}")

    print("ZIP açılıyor...")
    try:
        with zipfile.ZipFile(ZIP_PATH, "r") as z:
            z.extractall(EXTRACTED)
    except Exception as exc:
        fail(f"ZIP açılamadı: {exc}")

    candidates = list(EXTRACTED.rglob("EFI"))
    source = next((p for p in candidates if (p / "OC" / "config.plist").is_file()), None)
    if source is None:
        fail("ZIP içinde EFI\\OC\\config.plist bulunamadı.")

    print(f"EFI kaynağı: {source}")
    print("EFI bölümü bağlanıyor...")
    result = run(["mountvol", f"{DRIVE}\\", "/S"], check=False)
    if result.returncode != 0 or not Path(f"{DRIVE}\\EFI").exists():
        fail("EFI bölümü bağlanamadı. Yönetici CMD ile mountvol S: /S deneyin.")

    target = Path(f"{DRIVE}\\EFI")
    BACKUP.mkdir(parents=True, exist_ok=True)
    print(f"Mevcut EFI yedekleniyor: {BACKUP}")
    shutil.copytree(target, BACKUP / "EFI", dirs_exist_ok=True)

    # Preserve EFI\Microsoft and copy only the package's BOOT and OC folders.
    for name in ("BOOT", "OC"):
        src = source / name
        dst = target / name
        if src.exists():
            print(f"Kopyalanıyor: EFI\\{name}")
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            fail(f"Pakette EFI\\{name} bulunamadı.")

    oc = target / "OC" / "OpenCore.efi"
    config = target / "OC" / "config.plist"
    if not oc.is_file() or not config.is_file():
        fail("OpenCore.efi veya config.plist eksik.")

    print("Windows Boot Manager kaydı korunarak açılış yolu OpenCore yapılıyor...")
    result = run(["bcdedit", "/set", "{bootmgr}", "path", r"\EFI\OC\OpenCore.efi"], check=False)
    if result.returncode != 0:
        print(result.stdout, result.stderr)
        fail("BCD açılış yolu değiştirilemedi. EFI kopyalandı fakat Windows yolu değiştirilmedi.")

    print("\nTAMAMLANDI")
    print(f"- Yedek: {BACKUP / 'EFI'}")
    print(r"- Windows\EFI\Microsoft korunuyor.")
    print("- Sonraki açılışta OpenCore gelmeli.")
    print("- OpenCore menüsünde Windows görünmezse BIOS'tan Windows Boot Manager seçebilirsin.")
    print("\nGERİ ALMA (Yönetici CMD):")
    print(r"mountvol S: /S")
    print(r"bcdedit /set {bootmgr} path \EFI\Microsoft\Boot\bootmgfw.efi")
    print(r"mountvol S: /D")
    input("Kapatmak için Enter'a basın...")


if __name__ == "__main__":
    main()
