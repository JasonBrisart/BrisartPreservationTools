import os
import json
import uuid
import shutil
import hashlib
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime
from pathlib import Path


APP_NAME = "Physical Games Simulator"
APP_VERSION = "1.0.0"


def safe_name(name: str) -> str:
    cleaned = "".join(c for c in name if c.isalnum() or c in (" ", "_", "-")).strip()
    return cleaned.replace(" ", "_") or "Physical_Game"


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def copy_optional_source(source_path: str, destination_dir: Path):
    if not source_path:
        return None

    source = Path(source_path)
    if not source.exists():
        return None

    destination_dir.mkdir(parents=True, exist_ok=True)

    if source.is_file():
        target = destination_dir / source.name
        shutil.copy2(source, target)
        return str(target)

    if source.is_dir():
        target = destination_dir / source.name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)
        return str(target)

    return None


def generate_launcher_code(game_name: str, game_exe: str, disc_id: str) -> str:
    return f'''import os
import json
import subprocess
import tkinter as tk
from tkinter import messagebox
from pathlib import Path


GAME_NAME = {game_name!r}
GAME_EXE = {game_exe!r}
REQUIRED_DISC_ID = {disc_id!r}
TOKEN_FILE = "physical_disc_token.json"


def possible_roots():
    roots = []

    # Check Windows drive letters.
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        root = f"{{letter}}:\\\\"
        if os.path.exists(root):
            roots.append(root)

    # Also check the launcher's own folder and nearby folders.
    here = Path(__file__).resolve().parent
    roots.append(str(here))
    roots.append(str(here.parent))

    return roots


def find_disc_token():
    for root in possible_roots():
        token_path = Path(root) / TOKEN_FILE

        if token_path.exists():
            try:
                data = json.loads(token_path.read_text(encoding="utf-8"))
                if data.get("disc_id") == REQUIRED_DISC_ID:
                    return token_path, data
            except Exception:
                pass

        # Light recursive search, limited to avoid scanning entire hard drives too aggressively.
        try:
            root_path = Path(root)
            if root_path.exists():
                for candidate in root_path.glob("*/" + TOKEN_FILE):
                    try:
                        data = json.loads(candidate.read_text(encoding="utf-8"))
                        if data.get("disc_id") == REQUIRED_DISC_ID:
                            return candidate, data
                    except Exception:
                        pass
        except Exception:
            pass

    return None, None


def launch_game():
    token_path, token_data = find_disc_token()

    if not token_path:
        messagebox.showwarning(
            "Physical Disc Required",
            f"Insert the physical disc for {{GAME_NAME}}.\\n\\n"
            "You wanted physical games back. This is the friction. ;)\\n\\n"
            "Required token was not found."
        )
        return

    if not os.path.exists(GAME_EXE):
        messagebox.showerror(
            "Game Not Found",
            f"The configured game executable was not found:\\n\\n{{GAME_EXE}}"
        )
        return

    try:
        subprocess.Popen([GAME_EXE], cwd=os.path.dirname(GAME_EXE))
    except Exception as e:
        messagebox.showerror("Launch Failed", str(e))


def main():
    root = tk.Tk()
    root.title(f"{{GAME_NAME}} - Physical Launcher")
    root.geometry("520x280")
    root.resizable(False, False)

    tk.Label(
        root,
        text=f"{{GAME_NAME}}",
        font=("Segoe UI", 18, "bold")
    ).pack(pady=(24, 8))

    tk.Label(
        root,
        text="Physical Games Simulator",
        font=("Segoe UI", 11)
    ).pack()

    tk.Label(
        root,
        text="This launcher requires the matching physical disc/token to be present.",
        wraplength=440,
        justify="center",
        font=("Segoe UI", 10)
    ).pack(pady=18)

    tk.Button(
        root,
        text="Launch Game",
        command=launch_game,
        width=24,
        height=2
    ).pack(pady=8)

    tk.Label(
        root,
        text="Parody, but functional. No disc, no game. ;)",
        font=("Segoe UI", 9, "italic")
    ).pack(pady=(18, 0))

    root.mainloop()


if __name__ == "__main__":
    main()
'''


class PhysicalGamesSimulatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("760x620")
        self.root.resizable(False, False)

        self.game_name_var = tk.StringVar()
        self.game_exe_var = tk.StringVar()
        self.optional_source_var = tk.StringVar()
        self.output_folder_var = tk.StringVar()

        self.include_optional_var = tk.BooleanVar(value=True)

        self.build_ui()

    def build_ui(self):
        title = tk.Label(
            self.root,
            text="Physical Games Simulator",
            font=("Segoe UI", 22, "bold")
        )
        title.pack(pady=(20, 4))

        subtitle = tk.Label(
            self.root,
            text="A parody-but-functional tool for people who say they want physical games back.",
            font=("Segoe UI", 10)
        )
        subtitle.pack(pady=(0, 18))

        frame = tk.Frame(self.root)
        frame.pack(fill="both", expand=True, padx=28)

        self.add_labeled_entry(
            frame,
            "Game Name",
            self.game_name_var,
            row=0,
            button_text=None,
            button_command=None
        )

        self.add_labeled_entry(
            frame,
            "Game Executable (.exe)",
            self.game_exe_var,
            row=1,
            button_text="Browse",
            button_command=self.pick_game_exe
        )

        self.add_labeled_entry(
            frame,
            "Optional Installer / Archive / Folder",
            self.optional_source_var,
            row=2,
            button_text="Browse",
            button_command=self.pick_optional_source
        )

        check = tk.Checkbutton(
            frame,
            text="Copy optional installer/archive/folder into disc package",
            variable=self.include_optional_var,
            font=("Segoe UI", 9)
        )
        check.grid(row=3, column=1, sticky="w", pady=(0, 14))

        self.add_labeled_entry(
            frame,
            "Output Folder",
            self.output_folder_var,
            row=4,
            button_text="Browse",
            button_command=self.pick_output_folder
        )

        build_button = tk.Button(
            self.root,
            text="Build Physical Disc Package",
            command=self.build_package,
            width=32,
            height=2,
            font=("Segoe UI", 10, "bold")
        )
        build_button.pack(pady=18)

        info = tk.Text(
            self.root,
            height=12,
            width=86,
            wrap="word",
            font=("Consolas", 9)
        )
        info.pack(padx=24, pady=(4, 18))

        info.insert(
            "1.0",
            "What this creates:\\n"
            "- A DISC_CONTENTS folder you can burn to DVD/Blu-ray/USB.\\n"
            "- A physical_disc_token.json file that acts as the fake old-school disc check.\\n"
            "- A PC_LAUNCHER folder containing a launcher for the selected game.\\n"
            "- The launcher refuses to run unless the matching disc token is present.\\n\\n"
            "Important:\\n"
            "- This does not crack DRM.\\n"
            "- This does not modify the game.\\n"
            "- This works best with DRM-free games you legally own.\\n"
            "- This is a functional parody / ownership-friction simulator.\\n\\n"
            "The point:\\n"
            "People say they want physical games back. Fine. Insert the disc. ;)\\n"
        )
        info.configure(state="disabled")

    def add_labeled_entry(self, parent, label, variable, row, button_text=None, button_command=None):
        tk.Label(
            parent,
            text=label,
            font=("Segoe UI", 10, "bold")
        ).grid(row=row, column=0, sticky="w", pady=10)

        entry = tk.Entry(
            parent,
            textvariable=variable,
            width=66,
            font=("Segoe UI", 9)
        )
        entry.grid(row=row, column=1, sticky="w", pady=10, padx=(10, 8))

        if button_text and button_command:
            btn = tk.Button(
                parent,
                text=button_text,
                command=button_command,
                width=10
            )
            btn.grid(row=row, column=2, sticky="w", pady=10)

    def pick_game_exe(self):
        path = filedialog.askopenfilename(
            title="Select Game Executable",
            filetypes=[("Executable Files", "*.exe"), ("All Files", "*.*")]
        )
        if path:
            self.game_exe_var.set(path)

            if not self.game_name_var.get().strip():
                self.game_name_var.set(Path(path).stem)

    def pick_optional_source(self):
        choice = messagebox.askyesno(
            "Optional Source",
            "Choose YES to select a file.\\nChoose NO to select a folder."
        )

        if choice:
            path = filedialog.askopenfilename(
                title="Select Installer / Archive / File",
                filetypes=[("All Files", "*.*")]
            )
        else:
            path = filedialog.askdirectory(
                title="Select Folder"
            )

        if path:
            self.optional_source_var.set(path)

    def pick_output_folder(self):
        path = filedialog.askdirectory(title="Select Output Folder")
        if path:
            self.output_folder_var.set(path)

    def validate(self):
        game_name = self.game_name_var.get().strip()
        game_exe = self.game_exe_var.get().strip()
        output_folder = self.output_folder_var.get().strip()

        if not game_name:
            messagebox.showerror("Missing Game Name", "Enter a game name.")
            return False

        if not game_exe or not os.path.exists(game_exe):
            messagebox.showerror("Missing Game Executable", "Select a valid game executable.")
            return False

        if not output_folder:
            messagebox.showerror("Missing Output Folder", "Select an output folder.")
            return False

        return True

    def build_package(self):
        if not self.validate():
            return

        game_name = self.game_name_var.get().strip()
        game_exe = self.game_exe_var.get().strip()
        optional_source = self.optional_source_var.get().strip()
        output_folder = Path(self.output_folder_var.get().strip())

        safe = safe_name(game_name)
        disc_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat(timespec="seconds")

        package_root = output_folder / f"{safe}_Physical_Games_Simulator"
        disc_contents = package_root / "DISC_CONTENTS"
        pc_launcher = package_root / "PC_LAUNCHER"
        optional_dir = disc_contents / "OPTIONAL_INSTALLER_OR_ARCHIVE"

        if package_root.exists():
            overwrite = messagebox.askyesno(
                "Package Exists",
                f"The package already exists:\\n\\n{package_root}\\n\\nOverwrite it?"
            )
            if not overwrite:
                return
            shutil.rmtree(package_root)

        disc_contents.mkdir(parents=True, exist_ok=True)
        pc_launcher.mkdir(parents=True, exist_ok=True)

        game_hash = None
        try:
            game_hash = sha256_file(game_exe)
        except Exception:
            game_hash = "Could not hash executable."

        token = {
            "app": APP_NAME,
            "app_version": APP_VERSION,
            "disc_id": disc_id,
            "game_name": game_name,
            "created_at": created_at,
            "purpose": "Physical-disc presence token for parody-but-functional physical game simulation.",
            "notice": "This token does not provide DRM circumvention and does not modify the game."
        }

        manifest = {
            "app": APP_NAME,
            "app_version": APP_VERSION,
            "game_name": game_name,
            "game_executable": game_exe,
            "game_executable_sha256": game_hash,
            "disc_id": disc_id,
            "created_at": created_at,
            "disc_contents_folder": str(disc_contents),
            "pc_launcher_folder": str(pc_launcher),
            "optional_source_included": False,
            "optional_source_original_path": optional_source or None,
            "legal_notice": (
                "Use only with DRM-free games/software you legally own. "
                "This tool does not bypass DRM, remove DRM, crack software, or alter game files."
            )
        }

        write_json(disc_contents / "physical_disc_token.json", token)
        write_json(package_root / "manifest.json", manifest)

        if self.include_optional_var.get() and optional_source:
            copied = copy_optional_source(optional_source, optional_dir)
            if copied:
                manifest["optional_source_included"] = True
                manifest["optional_source_copied_to"] = copied
                write_json(package_root / "manifest.json", manifest)

        launcher_code = generate_launcher_code(game_name, game_exe, disc_id)
        launcher_path = pc_launcher / f"Launch_{safe}.py"
        write_text(launcher_path, launcher_code)

        readme = f"""# {game_name} - Physical Games Simulator Package

Generated by {APP_NAME} v{APP_VERSION}

This package recreates the old-school physical PC game experience:

Insert disc.
Run launcher.
Game launches only if the matching disc token is present.

## Folders

DISC_CONTENTS
- Burn this folder to a disc, copy it to USB, or store it as physical media.
- It contains physical_disc_token.json.
- The launcher searches for this token.

PC_LAUNCHER
- Contains the launcher for your game.
- Keep this launcher on your PC.
- Run it when you want to play.

## How To Use

1. Burn the contents of DISC_CONTENTS to a DVD, Blu-ray, or other physical media.
2. Keep the PC_LAUNCHER folder on your computer.
3. Insert the disc/media.
4. Run the launcher.
5. If the matching disc token is found, the game starts.
6. If the disc is missing, the launcher refuses.

## Important

This is a parody-but-functional simulator.

It does not:
- bypass DRM
- remove DRM
- crack games
- modify game files
- guarantee real copy protection

It is best used with DRM-free games/software you legally own.

## The Joke

People said they wanted physical games back.

So here it is.

No disc, no game. ;)

Disc ID:
{disc_id}

Created:
{created_at}
"""

        write_text(package_root / "README.txt", readme)
        write_text(disc_contents / "README_ON_DISC.txt", readme)

        messagebox.showinfo(
            "Package Built",
            f"Physical game package created successfully.\\n\\n{package_root}\\n\\n"
            "Burn DISC_CONTENTS to physical media, then use the launcher in PC_LAUNCHER."
        )


def main():
    root = tk.Tk()
    app = PhysicalGamesSimulatorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()