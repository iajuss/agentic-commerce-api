#!/usr/bin/env bash
# Publica o build do agentic-commerce-web sem derrubar o site. Cada build vira uma pasta em
# /var/www/agentic-commerce-web/versoes/, e o link "atual", que o nginx serve, troca de uma vez.
#
#   bash deploy/publicar-front.sh ARQUIVO.tar.gz COMMIT   publica o conteúdo de dist/ empacotado
#   bash deploy/publicar-front.sh --voltar                volta para a versão anterior
set -euo pipefail

BASE=/var/www/agentic-commerce-web
VERSOES="$BASE/versoes"
MANTER=5

versao_atual() {
    local alvo
    alvo="$(readlink "$BASE/atual" || true)"
    printf '%s' "${alvo##*/}"
}

apontar_para() {
    # O mv -T troca o link numa operação só: nenhuma requisição encontra o site sem front.
    ln -sfn "versoes/$1" "$BASE/atual.novo"
    mv -Tf "$BASE/atual.novo" "$BASE/atual"
}

assets_do_index() {
    grep -o '/assets/[^"]*' "$1/index.html" || true
}

conferir_arquivos() {
    # Um build do Vite tem o index.html e cita pelo menos um arquivo de /assets/, que precisa existir.
    local pasta="$1" assets asset
    [[ -f "$pasta/index.html" ]] || return 1
    assets="$(assets_do_index "$pasta")"
    [[ -n "$assets" ]] || return 1
    for asset in $assets; do
        [[ -f "$pasta$asset" ]] || return 1
    done
}

conferir_no_ar() {
    # O nginx precisa servir exatamente o index.html da versão e os arquivos que ele cita.
    local pasta="$VERSOES/$1" asset
    curl -fsS http://127.0.0.1/ | cmp -s - "$pasta/index.html" || return 1
    for asset in $(assets_do_index "$pasta"); do
        curl -fsS -o /dev/null "http://127.0.0.1$asset" || return 1
    done
}

podar() {
    # Guarda as $MANTER versões mais novas para o --voltar; a atual nunca é apagada.
    local atual="$1" velha
    for velha in $(ls -1 "$VERSOES" | sort | head -n -"$MANTER"); do
        if [[ "$velha" != "$atual" ]]; then
            rm -rf -- "${VERSOES:?}/$velha"
        fi
    done
}

publicar() {
    local arquivo="$1" commit="$2" anterior versao pasta
    if [[ ! -f "$arquivo" ]]; then
        printf 'Arquivo não encontrado: %s\n' "$arquivo" >&2
        exit 1
    fi
    if [[ ! "$commit" =~ ^[0-9a-f]{7,40}$ ]]; then
        printf 'Informe o commit do front publicado (7 a 40 caracteres hexadecimais).\n' >&2
        exit 1
    fi

    versao="$(date -u +%Y%m%d-%H%M%S)-$commit"
    pasta="$VERSOES/$versao"
    mkdir -p "$pasta"
    tar -xzf "$arquivo" -C "$pasta" --no-same-owner
    chmod -R u=rwX,go=rX "$pasta"
    if ! conferir_arquivos "$pasta"; then
        rm -rf -- "$pasta"
        printf 'O pacote não é um build do front: falta o index.html ou um arquivo de /assets/.\n' >&2
        exit 1
    fi

    anterior="$(versao_atual)"
    apontar_para "$versao"
    if ! conferir_no_ar "$versao"; then
        if [[ -n "$anterior" ]]; then
            apontar_para "$anterior"
            printf 'O nginx não serviu a versão %s; o front continua em %s.\n' "$versao" "$anterior" >&2
        else
            printf 'O nginx não serviu a versão %s; confira se o site usa root %s/atual.\n' "$versao" "$BASE" >&2
        fi
        exit 1
    fi

    podar "$versao"
    printf 'Front publicado: %s (antes: %s).\n' "$versao" "${anterior:-nenhuma}"
}

voltar() {
    local atual anterior
    atual="$(versao_atual)"
    anterior="$(ls -1 "$VERSOES" 2>/dev/null | sort | grep -x -B1 -F -- "$atual" | head -1 || true)"
    if [[ -z "$atual" || -z "$anterior" || "$anterior" == "$atual" ]]; then
        printf 'Não há versão anterior a %s.\n' "${atual:-(nenhuma)}" >&2
        exit 1
    fi

    apontar_para "$anterior"
    if ! conferir_no_ar "$anterior"; then
        apontar_para "$atual"
        printf 'O nginx não serviu a versão %s; o front continua em %s.\n' "$anterior" "$atual" >&2
        exit 1
    fi
    printf 'Front voltou para %s (antes: %s).\n' "$anterior" "$atual"
}

mkdir -p "$VERSOES"
# Duas publicações ao mesmo tempo poderiam apontar o link para a versão errada.
exec 9>"$BASE/.publicando"
if ! flock -n 9; then
    printf 'Outra publicação do front está em andamento.\n' >&2
    exit 1
fi

case "${1:-}" in
    --voltar)
        voltar
        ;;
    *)
        if [[ $# -ne 2 ]]; then
            printf 'Uso: bash deploy/publicar-front.sh ARQUIVO.tar.gz COMMIT | --voltar\n' >&2
            exit 1
        fi
        publicar "$1" "$2"
        ;;
esac
