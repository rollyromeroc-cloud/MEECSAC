# Voladura & Polvorín

App privada (Streamlit) para automatizar:

1. **Cálculo de perforación y voladura** por labor minera (galerías, cortadas,
   piques, chimeneas, estocadas): a partir de la sección del túnel y la malla
   de perforación, calcula taladros, explosivo (por tipo), accesorios
   (fulminantes, mecha), avance, volumen, tonelaje y factor de potencia.
2. **Verificación de seguridad de polvorín**: distancias reales (UTM) desde
   un polvorín a puntos de riesgo (poblados, vías, líneas férreas, etc.),
   área del cerco perimétrico, y mapa interactivo.

Ambos módulos generan un reporte Word (.docx) descargable con la misma
estructura que un informe técnico de perforación y voladura.

El motor de cálculo (`core/voladura.py`) fue validado contra los valores
reales de un informe técnico de referencia — ver `tests/test_voladura.py`.

## Ejecutar en local

```bash
pip install -r requirements.txt
streamlit run app.py
```

Para probar el gate de contraseña en local, crea `.streamlit/secrets.toml`
(NO se commitea, ver `.gitignore`) a partir de `secrets.toml.example`:

```toml
APP_PASSWORD = "tu-clave-aqui"
```

Si no existe `secrets.toml`, la app funciona sin contraseña (con una
advertencia en la barra lateral) — pensado solo para desarrollo local.

## Desplegar en Streamlit Community Cloud (gratis)

1. Sube este proyecto a un repositorio de GitHub (puede ser privado).
2. Entra a [share.streamlit.io](https://share.streamlit.io) con tu cuenta de
   GitHub.
3. "New app" → selecciona el repo, la rama, y como archivo principal:
   `voladura_polvorin_app/app.py` (si el repo contiene solo esta carpeta en
   la raíz, sería `app.py`).
4. En el panel de la app → **Settings → Secrets**, pega:
   ```toml
   APP_PASSWORD = "tu-clave-aqui"
   ```
   Esta es la contraseña que compartirás con las 2 personas más del equipo.
5. Deploy. La URL que te da Streamlit Cloud es la que usarán las 3
   computadoras (no depende de que ninguna laptop esté encendida).

## Compartir datos entre las 3 computadoras

Cada persona trabaja con sus propios datos en su sesión del navegador (no
hay base de datos compartida). Para compartir un proyecto:

1. En **📊 Programa General** → "Exportar" → descarga el archivo JSON.
2. Envíalo (correo, WhatsApp, etc.) a la otra persona.
3. En su computadora, en la misma sección → "Importar" → sube el archivo →
   elige "Reemplazar todo" o "Agregar a lo existente".

## Estructura del proyecto

```
core/       # Lógica de cálculo pura (sin Streamlit) — testeable con pytest
reports/    # Generación de reportes Word (python-docx)
pages/      # Páginas de la app (Voladura, Polvorín, Programa General)
tests/      # pytest — incluye golden tests contra un informe técnico real
app.py      # Página de inicio / navegación
auth.py     # Gate de contraseña
```

## Notas importantes

- Las **distancias mínimas de seguridad** del módulo de polvorín se ingresan
  manualmente en la app — no vienen precargadas de ningún reglamento.
  Verifícalas contra el D.S. N.° 024-2016-EM y sus modificatorias antes de
  usarlas para decisiones operativas.
- La URL de Streamlit Community Cloud es técnicamente accesible por
  internet (no indexada, pero no es privada en un sentido estricto). El gate
  de contraseña es una medida básica, no un control de acceso robusto.
