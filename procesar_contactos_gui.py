"""
Procesador de contactos DENUE — Interfaz Gráfica (Modo CSV y Match)
"""
import pandas as pd
import re
import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ─────────────────── CONFIGURACIÓN ───────────────────
# Definimos las columnas exactas que buscará y dejará el programa
COL_CORREO    = "correoelec"
COL_EMPRESA   = "nom_estab"
COL_ESTADO    = "entidad"
COL_MUNICIPIO = "municipio"

PATRON_CORREO = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)
PATRON_GOBIERNO = re.compile(r"@(.+\.)?gob\.mx$|@(.+\.)?gobierno\.mx$")
# ─────────────────────────────────────────────────────

def es_correo_valido(c):
    return isinstance(c, str) and bool(PATRON_CORREO.match(c.strip()))

def es_correo_gobierno(c):
    if not isinstance(c, str):
        return False
    return bool(PATRON_GOBIERNO.search(c.strip().lower()))

def sanitizar(nombre):
    # Limpia caracteres especiales para evitar errores al crear archivos
    return re.sub(r'[\\/*?:"<>|]', "", str(nombre)).strip()

# ══════════════════════ LÓGICA DE PROCESAMIENTO ══════════════════════

def procesar_separar_municipios(entrada, carpeta_salida, log):
    log("Leyendo archivo de entrada...")
    
    try:
        # Detectar si el archivo es CSV o Excel
        if entrada.lower().endswith('.csv'):
            try:
                df = pd.read_csv(entrada, dtype=str, encoding='utf-8')
            except UnicodeDecodeError:
                df = pd.read_csv(entrada, dtype=str, encoding='latin1')
        else:
            df = pd.read_excel(entrada, dtype=str)
            
        # Estandarizar nombres de columnas a minúsculas
        df.columns = df.columns.str.strip().str.lower()
        log(f"  Filas totales leídas: {len(df)}")
        
    except Exception as e:
        raise ValueError(f"Error al leer el archivo de entrada: {e}")

    columnas_requeridas = [COL_CORREO, COL_EMPRESA, COL_ESTADO, COL_MUNICIPIO]
    for col in columnas_requeridas:
        if col not in df.columns:
            raise ValueError(f"Falta la columna '{col}'.\nColumnas disponibles: {list(df.columns)}")

    # Limpieza básica
    antes = len(df)
    df = df[df[COL_CORREO].notna() & (df[COL_CORREO].str.strip() != "")]
    log(f"  Sin correo eliminados: {antes - len(df)}")

    df[COL_CORREO] = df[COL_CORREO].str.strip().str.lower()

    antes = len(df)
    df = df[df[COL_CORREO].apply(es_correo_valido)]
    log(f"  Correos mal escritos eliminados: {antes - len(df)}")

    antes = len(df)
    df = df[~df[COL_CORREO].apply(es_correo_gobierno)]
    log(f"  Correos gobierno eliminados: {antes - len(df)}")

    antes = len(df)
    df = df.drop_duplicates(subset=[COL_CORREO], keep="first")
    log(f"  Duplicados eliminados: {antes - len(df)}")

    # Identificar municipios únicos
    municipios = df[COL_MUNICIPIO].fillna("SIN_MUNICIPIO").str.strip().unique()
    log(f"\nMunicipios encontrados: {len(municipios)}")

    os.makedirs(carpeta_salida, exist_ok=True)

    for mun in sorted(municipios):
        df_m = df[df[COL_MUNICIPIO].fillna("SIN_MUNICIPIO").str.strip() == mun].copy()
        
        # Conservar SOLO las 3 columnas solicitadas
        df_m = df_m[[COL_CORREO, COL_EMPRESA, COL_ESTADO]]
        df_m = df_m.sort_values(COL_CORREO)
        
        mun_seguro = sanitizar(mun)
        total_registros = len(df_m)
        chunk_size = 5000
        
        # Separar en archivos si excede 5000
        idx_archivo = 1
        for i in range(0, total_registros, chunk_size):
            df_chunk = df_m.iloc[i : i + chunk_size]
            
            if total_registros > chunk_size:
                nombre_csv = f"{mun_seguro}_{idx_archivo}.csv"
            else:
                nombre_csv = f"{mun_seguro}.csv"
                
            ruta_final = os.path.join(carpeta_salida, nombre_csv)
            # utf-8-sig preserva tildes y eñes al abrir el CSV en Excel
            df_chunk.to_csv(ruta_final, index=False, encoding="utf-8-sig")
            idx_archivo += 1

        log(f"  → {mun_seguro}: {total_registros} registros guardados.")

    log(f"\n✅ ¡Listo! CSVs generados en la carpeta:\n   {carpeta_salida}")


def procesar_match_correos(entrada_base, archivos_match, archivo_salida, log):
    log("Leyendo archivo base principal...")
    
    try:
        # Detectar si la base es CSV o Excel
        if entrada_base.lower().endswith('.csv'):
            try:
                df_base = pd.read_csv(entrada_base, dtype=str, encoding='utf-8')
            except UnicodeDecodeError:
                df_base = pd.read_csv(entrada_base, dtype=str, encoding='latin1')
        else:
            df_base = pd.read_excel(entrada_base, dtype=str)
            
        df_base.columns = df_base.columns.str.strip().str.lower()
        log(f"  Filas leídas: {len(df_base)}")
    except Exception as e:
        raise ValueError(f"Error al leer el archivo base: {e}")

    columnas_requeridas = [COL_CORREO, COL_EMPRESA, COL_ESTADO]
    for col in columnas_requeridas:
        if col not in df_base.columns:
            raise ValueError(f"Falta la columna '{col}' en la base.\nColumnas disponibles: {list(df_base.columns)}")

    correos_match = set()
    for ruta in archivos_match:
        log(f"Extrayendo correos de: {os.path.basename(ruta)}")
        try:
            if ruta.lower().endswith('.csv'):
                try:
                    df_ext = pd.read_csv(ruta, dtype=str, encoding='utf-8')
                except UnicodeDecodeError:
                    df_ext = pd.read_csv(ruta, dtype=str, encoding='latin1')
            else:
                df_ext = pd.read_excel(ruta, dtype=str)
            
            df_ext.columns = df_ext.columns.str.strip().str.lower()
            col_email = None
            
            # Buscar columna que parezca correo
            for c in df_ext.columns:
                if 'correo' in c or 'email' in c:
                    col_email = c
                    break
            if not col_email and len(df_ext.columns) > 0:
                col_email = df_ext.columns[0] 

            if col_email:
                lista_c = df_ext[col_email].dropna().str.strip().str.lower().unique()
                correos_match.update(lista_c)
                log(f"  → Se agregaron {len(lista_c)} correos únicos.")
        except Exception as e:
            log(f"  ⚠️ Error procesando {os.path.basename(ruta)}: {e}")

    log(f"\nTotal de correos externos recopilados para hacer match: {len(correos_match)}")

    df_base[COL_CORREO] = df_base[COL_CORREO].fillna("").str.strip().str.lower()
    antes = len(df_base)
    
    # Hacer el cruce/match
    df_filtrado = df_base[df_base[COL_CORREO].isin(correos_match)].copy()
    log(f"Coincidencias encontradas: {len(df_filtrado)} (Se eliminaron {antes - len(df_filtrado)} filas)")

    # Conservar SOLO las 3 columnas solicitadas
    df_filtrado = df_filtrado[[COL_CORREO, COL_EMPRESA, COL_ESTADO]]
    df_filtrado = df_filtrado.sort_values(COL_CORREO)

    df_filtrado.to_csv(archivo_salida, index=False, encoding="utf-8-sig")
    log(f"\n✅ ¡Match completado! Archivo unificado guardado en:\n   {archivo_salida}")


# ══════════════════════ INTERFAZ GRÁFICA ══════════════════════════════

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Procesador de Contactos DENUE - Avanzado")
        self.resizable(False, False)
        self.configure(bg="#1e1e2e")
        self.archivos_externos = []
        self._build()

    def _build(self):
        PAD = dict(padx=14, pady=6)
        BG  = "#1e1e2e"
        FG  = "#cdd6f4"
        ACC = "#89b4fa"
        BTN = "#313244"
        FONT_H = ("Segoe UI", 11, "bold")
        FONT_N = ("Segoe UI", 10)

        # ── Título ──
        tk.Label(self, text="Procesador de Contactos DENUE",
                 bg=BG, fg=ACC, font=("Segoe UI", 14, "bold")).pack(pady=(18, 4))
        tk.Label(self, text="Exportación 100% en CSV",
                 bg=BG, fg="#a6adc8", font=FONT_N).pack(pady=(0, 12))

        # ── Selector de Modo ──
        frm_radio = tk.LabelFrame(self, text=" ¿Qué deseas hacer? ", bg=BG, fg=ACC, font=FONT_H, padx=10, pady=5)
        frm_radio.pack(fill="x", **PAD)

        self.modo_var = tk.IntVar(value=1)
        tk.Radiobutton(frm_radio, text="1. Separar por Municipios (Max 5000 registros por CSV)", variable=self.modo_var, value=1, 
                       bg=BG, fg=FG, selectcolor=BTN, activebackground=BG, activeforeground=ACC, font=FONT_N, command=self._toggle_modo).pack(anchor="w")
        tk.Radiobutton(frm_radio, text="2. Cruzar datos (Match de correos externos con mi Base)", variable=self.modo_var, value=2, 
                       bg=BG, fg=FG, selectcolor=BTN, activebackground=BG, activeforeground=ACC, font=FONT_N, command=self._toggle_modo).pack(anchor="w")

        # ── Contenedores Dinámicos ──
        self.frm_opcion1 = tk.Frame(self, bg=BG)
        self.frm_opcion2 = tk.Frame(self, bg=BG)

        # ----- UI OPCIÓN 1 -----
        f1_in = tk.Frame(self.frm_opcion1, bg=BG); f1_in.pack(fill="x", pady=4)
        tk.Label(f1_in, text="Archivo Entrada:", bg=BG, fg=FG, font=FONT_N, width=22, anchor="w").pack(side="left")
        self.var_in1 = tk.StringVar()
        tk.Entry(f1_in, textvariable=self.var_in1, width=38, bg=BTN, fg=FG, insertbackground=FG, relief="flat", font=FONT_N).pack(side="left", padx=4)
        tk.Button(f1_in, text="📂 Buscar", command=self._buscar_in1, bg=ACC, fg="#1e1e2e", font=FONT_H, relief="flat", cursor="hand2", padx=4).pack(side="left")

        f1_out = tk.Frame(self.frm_opcion1, bg=BG); f1_out.pack(fill="x", pady=4)
        tk.Label(f1_out, text="Carpeta de Salida:", bg=BG, fg=FG, font=FONT_N, width=22, anchor="w").pack(side="left")
        self.var_out1 = tk.StringVar()
        tk.Entry(f1_out, textvariable=self.var_out1, width=38, bg=BTN, fg=FG, insertbackground=FG, relief="flat", font=FONT_N).pack(side="left", padx=4)
        tk.Button(f1_out, text="📁 Destino", command=self._buscar_out1, bg=ACC, fg="#1e1e2e", font=FONT_H, relief="flat", cursor="hand2", padx=4).pack(side="left")

        # ----- UI OPCIÓN 2 -----
        f2_base = tk.Frame(self.frm_opcion2, bg=BG); f2_base.pack(fill="x", pady=4)
        tk.Label(f2_base, text="Archivo Base:", bg=BG, fg=FG, font=FONT_N, width=22, anchor="w").pack(side="left")
        self.var_base2 = tk.StringVar()
        tk.Entry(f2_base, textvariable=self.var_base2, width=38, bg=BTN, fg=FG, insertbackground=FG, relief="flat", font=FONT_N).pack(side="left", padx=4)
        tk.Button(f2_base, text="📂 Buscar", command=self._buscar_base2, bg=ACC, fg="#1e1e2e", font=FONT_H, relief="flat", cursor="hand2", padx=4).pack(side="left")

        f2_match = tk.Frame(self.frm_opcion2, bg=BG); f2_match.pack(fill="x", pady=4)
        tk.Label(f2_match, text="Archivos para Match:", bg=BG, fg=FG, font=FONT_N, width=22, anchor="w").pack(side="left")
        self.var_match2 = tk.StringVar(value="0 archivos seleccionados")
        tk.Entry(f2_match, textvariable=self.var_match2, width=38, bg=BTN, fg=FG, state="readonly", relief="flat", font=FONT_N).pack(side="left", padx=4)
        tk.Button(f2_match, text="➕ Agregar", command=self._buscar_match2, bg=ACC, fg="#1e1e2e", font=FONT_H, relief="flat", cursor="hand2", padx=4).pack(side="left")

        f2_out = tk.Frame(self.frm_opcion2, bg=BG); f2_out.pack(fill="x", pady=4)
        tk.Label(f2_out, text="CSV Final de Salida:", bg=BG, fg=FG, font=FONT_N, width=22, anchor="w").pack(side="left")
        self.var_out2 = tk.StringVar()
        tk.Entry(f2_out, textvariable=self.var_out2, width=38, bg=BTN, fg=FG, insertbackground=FG, relief="flat", font=FONT_N).pack(side="left", padx=4)
        tk.Button(f2_out, text="💾 Guardar", command=self._buscar_out2, bg=ACC, fg="#1e1e2e", font=FONT_H, relief="flat", cursor="hand2", padx=4).pack(side="left")

        self.frm_opcion1.pack(fill="x", **PAD) # Mostrar modo 1 por defecto

        # ── Botón procesar ──
        self.btn = tk.Button(self, text="▶  EJECUTAR TAREA", command=self._iniciar, bg="#a6e3a1", fg="#1e1e2e", font=("Segoe UI", 12, "bold"), relief="flat", cursor="hand2", padx=20, pady=6)
        self.btn.pack(pady=10)

        # ── Barra progreso y Log ──
        self.progress = ttk.Progressbar(self, mode="indeterminate", length=490)
        self.progress.pack(pady=(0,8))
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TProgressbar", troughcolor=BTN, background=ACC, thickness=6)

        frm3 = tk.Frame(self, bg=BG); frm3.pack(fill="both", expand=True, padx=14, pady=(0,14))
        self.txt = tk.Text(frm3, height=12, width=62, bg=BTN, fg=FG, font=("Consolas", 9), relief="flat", state="disabled", wrap="word")
        sb = tk.Scrollbar(frm3, command=self.txt.yview, bg=BTN)
        self.txt.configure(yscrollcommand=sb.set)
        self.txt.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    def _toggle_modo(self):
        if self.modo_var.get() == 1:
            self.frm_opcion2.pack_forget()
            self.frm_opcion1.pack(fill="x", padx=14, pady=6)
        else:
            self.frm_opcion1.pack_forget()
            self.frm_opcion2.pack(fill="x", padx=14, pady=6)

    def _log(self, msg):
        self.txt.configure(state="normal")
        self.txt.insert("end", msg + "\n")
        self.txt.see("end")
        self.txt.configure(state="disabled")

    # Búsquedas Modo 1
    def _buscar_in1(self):
        path = filedialog.askopenfilename(title="Selecciona archivo (Excel o CSV)", filetypes=[("Archivos de Datos", "*.xlsx *.xls *.xlsm *.xlsb *.csv")])
        if path:
            self.var_in1.set(path)
            self.var_out1.set(os.path.join(os.path.dirname(path), "CSVs_Por_Municipio"))

    def _buscar_out1(self):
        path = filedialog.askdirectory(title="Carpeta destino para los CSVs")
        if path:
            self.var_out1.set(path)

    # Búsquedas Modo 2
    def _buscar_base2(self):
        path = filedialog.askopenfilename(title="Selecciona archivo Base (Excel o CSV)", filetypes=[("Archivos de Datos", "*.xlsx *.xls *.xlsm *.xlsb *.csv")])
        if path:
            self.var_base2.set(path)
            self.var_out2.set(os.path.splitext(path)[0] + "_MATCH.csv")

    def _buscar_match2(self):
        paths = filedialog.askopenfilenames(title="Archivos para extraer correos (Excel/CSV)", filetypes=[("Excel/CSV", "*.xlsx *.xls *.csv")])
        if paths:
            self.archivos_externos = list(paths)
            self.var_match2.set(f"{len(paths)} archivo(s) listo(s)")

    def _buscar_out2(self):
        path = filedialog.asksaveasfilename(title="Guardar CSV resultante", defaultextension=".csv", filetypes=[("Archivo CSV", "*.csv")])
        if path:
            self.var_out2.set(path)

    # Procesamiento con Hilos
    def _iniciar(self):
        modo = self.modo_var.get()
        
        if modo == 1:
            entrada = self.var_in1.get().strip()
            salida = self.var_out1.get().strip()
            if not entrada or not salida:
                messagebox.showwarning("Aviso", "Llenar campos de Entrada y Carpeta Salida")
                return
            target_func = lambda: procesar_separar_municipios(entrada, salida, self._log)
        else:
            base = self.var_base2.get().strip()
            salida = self.var_out2.get().strip()
            if not base or not salida or not self.archivos_externos:
                messagebox.showwarning("Aviso", "Llenar campos Base, Match y Salida")
                return
            target_func = lambda: procesar_match_correos(base, self.archivos_externos, salida, self._log)

        self.btn.configure(state="disabled")
        self.progress.start(10)
        self._log(f"{'─'*55}\nIniciando Operación Modo {modo}...")

        def tarea():
            try:
                target_func()
                self.after(0, lambda: messagebox.showinfo("¡Listo!", "Proceso completado correctamente."))
            except Exception as e:
                self._log(f"\n❌ ERROR: {e}")
                self.after(0, lambda: messagebox.showerror("Error", str(e)))
            finally:
                self.after(0, self.progress.stop)
                self.after(0, lambda: self.btn.configure(state="normal"))

        threading.Thread(target=tarea, daemon=True).start()

if __name__ == "__main__":
    app = App()
    app.mainloop()