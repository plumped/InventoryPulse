#!/bin/bash
cd docs
mkdocs build
mkdir -p ../static/docs
cp -R site/* ../static/docs/
echo "Dokumentation erfolgreich in static/docs/ kopiert!"