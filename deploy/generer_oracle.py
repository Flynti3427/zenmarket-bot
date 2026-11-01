"""Regénère deploy/oracle-zenmarket.sh après une modification du code ou de config.yaml.

Usage : python deploy/generer_oracle.py
Le code est embarqué sans commentaires (limite Oracle : 32 000 octets pour le script cloud-init).
"""
import ast
import base64
import io
import pathlib
import re
import tarfile

import yaml

RACINE = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = RACINE / "deploy" / "oracle-zenmarket.sh"
LIMITE = 32_000


def sans_docstrings(code: str) -> str:
    arbre = ast.parse(code)
    for n in ast.walk(arbre):
        if (isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.body
                and isinstance(n.body[0], ast.Expr) and isinstance(getattr(n.body[0], "value", None), ast.Constant)
                and isinstance(n.body[0].value.value, str)):
            n.body = n.body[1:] or [ast.Pass()]
    return ast.unparse(arbre) + "\n"


def ajouter(tar: tarfile.TarFile, nom: str, contenu: str):
    data = contenu.encode()
    info = tarfile.TarInfo(nom)
    info.size = len(data)
    tar.addfile(info, io.BytesIO(data))


def main():
    tampon = io.BytesIO()
    with tarfile.open(fileobj=tampon, mode="w:xz", preset=9) as tar:
        for f in sorted((RACINE / "bot").rglob("*.py")):
            if f.name == "prix_max.py" or "__pycache__" in f.parts:
                continue
            ajouter(tar, str(f.relative_to(RACINE)), sans_docstrings(f.read_text(encoding="utf-8")))
        cfg = yaml.safe_load((RACINE / "config.yaml").read_text(encoding="utf-8"))
        ajouter(tar, "config.yaml", yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False, width=200))
        ajouter(tar, "requirements.txt", (RACINE / "requirements.txt").read_text(encoding="utf-8"))
    b64 = base64.encodebytes(tampon.getvalue()).decode().strip()
    texte = SCRIPT.read_text(encoding="utf-8")
    texte = re.sub(r"(base64 -d > bot\.txz <<'CODE'\n).*?(\nCODE\n)", lambda m: m.group(1) + b64 + m.group(2),
                   texte, flags=re.S)
    SCRIPT.write_text(texte, encoding="utf-8")
    taille = len(texte.encode())
    print(f"{SCRIPT.name} : {taille} octets (limite Oracle {LIMITE})")
    if taille > LIMITE:
        raise SystemExit("Trop gros pour Oracle : réduis le code ou la config.")


if __name__ == "__main__":
    main()
