#!/usr/bin/env bash
# SUDPUBLIK — o'rnatish skripti (Linux)
# Binarni ~/.local ga o'rnatadi va ilovalar menyusiga qo'shadi.
# Ishga tushirish:  ./install.sh

set -e

# Skript joylashgan papka (binar va ikonka shu yerda turibdi)
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

BIN_SRC="$SRC_DIR/SUDPUBLIK"
ICON_SRC="$SRC_DIR/icon.png"

BIN_DIR="$HOME/.local/bin"
ICON_DIR="$HOME/.local/share/icons"
APP_DIR="$HOME/.local/share/applications"

if [ ! -f "$BIN_SRC" ]; then
    echo "❌ Xato: SUDPUBLIK fayli topilmadi ($BIN_SRC)"
    exit 1
fi

echo "📦 SUDPUBLIK o'rnatilmoqda..."

mkdir -p "$BIN_DIR" "$ICON_DIR" "$APP_DIR"

# Binarni nusxalash va ishga tushirish ruxsatini berish
install -m 755 "$BIN_SRC" "$BIN_DIR/SUDPUBLIK"
echo "  ✅ Binar:  $BIN_DIR/SUDPUBLIK"

# Ikonkani nusxalash (mavjud bo'lsa)
ICON_LINE=""
if [ -f "$ICON_SRC" ]; then
    cp "$ICON_SRC" "$ICON_DIR/sudpublik.png"
    ICON_LINE="Icon=$ICON_DIR/sudpublik.png"
    echo "  ✅ Ikonka: $ICON_DIR/sudpublik.png"
fi

# Ilovalar menyusi uchun .desktop fayl yaratish
DESKTOP_FILE="$APP_DIR/SUDPUBLIK.desktop"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=SUDPUBLIK
Comment=Sud hujjatlarini avtomatik yuklab oluvchi
Exec=$BIN_DIR/SUDPUBLIK
$ICON_LINE
Terminal=false
Categories=Utility;Office;
EOF
chmod +x "$DESKTOP_FILE"
echo "  ✅ Menyu:  $DESKTOP_FILE"

# Menyu keshini yangilash (mavjud bo'lsa)
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true
fi

echo ""
echo "✅ Tayyor! Endi 'SUDPUBLIK' ni ilovalar menyusidan topib ishga tushiring."
echo "   Yoki terminalda:  SUDPUBLIK"
echo ""
echo "ℹ️  Agar terminalda 'command not found' chiqsa, \$HOME/.local/bin ni"
echo "   PATH ga qo'shing yoki tizimdan chiqib qayta kiring."
