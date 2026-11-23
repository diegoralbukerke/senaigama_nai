"""
Embute as imagens e os vídeos da pasta midia/ dentro do NAI-IA-SENAI-Gama.html.

Por que existe: a NAI é um HTML único que funciona com dois cliques, sem servidor web.
Por isso a imagem do avatar e os vídeos ficam DENTRO do HTML, codificados em base64.
Trocar um arquivo em midia/ não muda nada sozinho: rode este script depois.

Uso (na pasta do projeto):
    python ferramentas/embutir_midia.py            -> grava o HTML atualizado
    python ferramentas/embutir_midia.py --conferir -> só diz se o HTML já bate com a pasta midia/

Arquivo em midia/                    -> onde entra no HTML
  imagens/nai-avatar-2d.webp         -> const AVATAR_2D   (avatar parado, modo 2D)
  videos/nai-boas-vindas.mp4         -> ASSETS.welcome    (saudação)
  videos/nai-aceno-1.mp4, -2.mp4     -> ASSETS.oi         (aceno curto, sorteia um)
  videos/nai-parada-loop-1.mp4, -2   -> ASSETS.idle       (NAI parada, em loop)
  videos/nai-fala-divulgacao.mp4     -> ASSETS.lang.pt    (a fala sobre os cursos)

Os vídeos precisam ter FUNDO VERDE (o HTML recorta o verde) e o mesmo enquadramento dos originais.
"""
import base64
import json
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
HTML = RAIZ / "NAI-IA-SENAI-Gama.html"
MIDIA = RAIZ / "midia"


def data_url(caminho, mime):
    return f"data:{mime};base64," + base64.b64encode(caminho.read_bytes()).decode()


def video(nome):
    return data_url(MIDIA / "videos" / nome, "video/mp4")


def main():
    html = HTML.read_text(encoding="utf-8")

    m = re.search(r"const ASSETS = (\{.*?\});\n", html)
    if not m:
        sys.exit("Não achei 'const ASSETS' no HTML.")
    assets = json.loads(m.group(1))
    assets["welcome"] = [video("nai-boas-vindas.mp4")]
    assets["oi"] = [video("nai-aceno-1.mp4"), video("nai-aceno-2.mp4")]
    assets["idle"] = [video("nai-parada-loop-1.mp4"), video("nai-parada-loop-2.mp4")]
    assets["lang"]["pt"] = video("nai-fala-divulgacao.mp4")
    novo = html[:m.start(1)] + json.dumps(assets, ensure_ascii=False) + html[m.end(1):]

    avatar = data_url(MIDIA / "imagens" / "nai-avatar-2d.webp", "image/webp")
    novo = re.sub(r"const AVATAR_2D = '[^']*'", lambda _: f"const AVATAR_2D = '{avatar}'", novo, count=1)

    if "--conferir" in sys.argv:
        print("OK: o HTML já está igual à pasta midia/." if novo == html
              else "DIFERENTE: rode sem --conferir para atualizar o HTML.")
        return
    HTML.write_text(novo, encoding="utf-8")
    print(f"Pronto: {HTML.name} atualizado ({len(novo) / 1e6:.1f} MB).")


if __name__ == "__main__":
    main()
