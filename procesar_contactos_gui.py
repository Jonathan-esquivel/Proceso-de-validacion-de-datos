"""
Procesador de contactos DENUE — Interfaz Gráfica (Multifunción y Unificador)
"""
import pandas as pd
import re
import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ─────────────────── CONFIGURACIÓN DE CORREOS ───────────────────
PATRON_CORREO = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)
PATRON_GOBIERNO = re.compile(r"@(.+\.)?gob\.mx$|@(.+\.)?gobierno\.mx$")
# ──────────────────────────────────────────────────────────────

def es_correo_valido(c):
    return isinstance(c, str) and bool(PATRON_CORREO.match(c.strip()))

def es_correo_gobierno(c):
    if not isinstance(c, str):
        return False
    return bool(PATRON_GOBIERNO.search(c.strip().lower()))

def sanitizar(nombre):
    return re.sub(r'[\\/*?:"<>|]', "", str(nombre)).strip()

# ══════════════════════ LÓGICA DE PROCESAMIENTO ══════════════════════

def procesar_separar_municipios(rutas_entrada, carpeta_salida, log):
    log("Iniciando consolidación de archivos para separar...")
    
    dfs = []
    
    # Unir todos los archivos de entrada seleccionados
    for entrada in rutas_entrada:
        log(f"Leyendo archivo: {os.path.basename(entrada)}")
        try:
            if entrada.lower().endswith('.csv'):
                try:
                    df_temp = pd.read_csv(entrada, dtype=str, encoding='utf-8')
                except UnicodeDecodeError:
                    df_temp = pd.read_csv(entrada, dtype=str, encoding='latin1')
            else:
                df_temp = pd.read_excel(entrada, dtype=str)
                
            df_temp.columns = df_temp.columns.str.strip().str.lower()
            
            columnas_requeridas = ['correoelec', 'nom_estab', 'entidad', 'municipio']
            faltantes = [col for col in columnas_requeridas if col not in df_temp.columns]
            if faltantes:
                raise ValueError(f"Faltan las siguientes columnas: {faltantes} en {os.path.basename(entrada)}.\nColumnas disponibles: {list(df_temp.columns)}")
                
            dfs.append(df_temp[columnas_requeridas])
        except Exception as e:
            raise ValueError(f"Error al leer el archivo {os.path.basename(entrada)}: {e}")

    df = pd.concat(dfs, ignore_index=True)
    log(f"\n  Filas totales consolidadas: {len(df)}")

    # Limpieza Estricta
    antes = len(df)
    df = df[df['correoelec'].notna() & (df['correoelec'].str.strip() != "")]
    log(f"  Sin correo eliminados: {antes - len(df)}")

    df['correoelec'] = df['correoelec'].str.strip().str.lower()

    antes = len(df)
    df = df[df['correoelec'].apply(es_correo_valido)]
    log(f"  Correos mal escritos eliminados: {antes - len(df)}")

    antes = len(df)
    df = df[~df['correoelec'].apply(es_correo_gobierno)]
    log(f"  Correos gobierno eliminados: {antes - len(df)}")

    antes = len(df)
    df = df.drop_duplicates(subset=['correoelec'], keep="first")
    log(f"  Duplicados eliminados: {antes - len(df)}")

    municipios = df['municipio'].fillna("SIN_MUNICIPIO").str.strip().unique()
    log(f"\nMunicipios encontrados: {len(municipios)}")

    os.makedirs(carpeta_salida, exist_ok=True)

    for mun in sorted(municipios):
        df_m = df[df['municipio'].fillna("SIN_MUNICIPIO").str.strip() == mun].copy()
        
        df_m = df_m[['correoelec', 'nom_estab', 'entidad', 'municipio']]
        df_m = df_m.sort_values('correoelec')
        
        mun_seguro = sanitizar(mun)
        total_registros = len(df_m)
        chunk_size = 5000
        
        idx_archivo = 1
        for i in range(0, total_registros, chunk_size):
            df_chunk = df_m.iloc[i : i + chunk_size]
            
            if total_registros > chunk_size:
                nombre_csv = f"{mun_seguro}_{idx_archivo}.csv"
            else:
                nombre_csv = f"{mun_seguro}.csv"
                
            ruta_final = os.path.join(carpeta_salida, nombre_csv)
            df_chunk.to_csv(ruta_final, index=False, encoding="utf-8-sig")
            idx_archivo += 1

        log(f"  → {mun_seguro}: {total_registros} registros guardados.")

    log(f"\n✅ ¡Listo! CSVs generados en la carpeta:\n   {carpeta_salida}")


def procesar_match_correos(rutas_base, archivos_match, archivo_salida, log):
    log("Iniciando consolidación de múltiples archivos Base...")
    
    dfs_base = []
    
    for ruta in rutas_base:
        log(f"Leyendo base: {os.path.basename(ruta)}")
        try:
            if ruta.lower().endswith('.csv'):
                try:
                    df_temp = pd.read_csv(ruta, dtype=str, encoding='utf-8')
                except UnicodeDecodeError:
                    df_temp = pd.read_csv(ruta, dtype=str, encoding='latin1')
            else:
                df_temp = pd.read_excel(ruta, dtype=str)
                
            df_temp.columns = df_temp.columns.str.strip().str.lower()
            
            columnas_match = ['correoelec', 'nom_estab', 'municipio']
            faltantes = [c for c in columnas_match if c not in df_temp.columns]
            if faltantes:
                raise ValueError(f"Faltan columnas {faltantes} en el archivo {os.path.basename(ruta)}")
                
            dfs_base.append(df_temp[columnas_match])
        except Exception as e:
            raise ValueError(f"Error procesando la base {os.path.basename(ruta)}: {e}")

    df_base = pd.concat(dfs_base, ignore_index=True)
    log(f"\nTotal de filas consolidadas de TODAS las bases: {len(df_base)}")

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
            
            for c in df_ext.columns:
                if 'correo' in c or 'email' in c or 'correoelec' in c:
                    col_email = c
                    break
            if not col_email and len(df_ext.columns) > 0:
                col_email = df_ext.columns[0] 

            if col_email:
                lista_c = df_ext[col_email].dropna().str.strip().str.lower().unique()
                correos_match.update(lista_c)
                log(f"  → Se agregaron {len(lista_c)} correos únicos desde '{col_email}'.")
        except Exception as e:
            log(f"  ⚠️ Error procesando {os.path.basename(ruta)}: {e}")

    log(f"\nTotal de correos externos recopilados para hacer match: {len(correos_match)}")

    df_base['correoelec'] = df_base['correoelec'].fillna("").str.strip().str.lower()
    antes = len(df_base)
    
    df_filtrado = df_base[df_base['correoelec'].isin(correos_match)].copy()
    log(f"Coincidencias encontradas: {len(df_filtrado)} (Se eliminaron {antes - len(df_filtrado)} filas)")

    df_filtrado = df_filtrado[['correoelec', 'nom_estab', 'municipio']]
    df_filtrado = df_filtrado.sort_values('correoelec')

    df_filtrado.to_csv(archivo_salida, index=False, encoding="utf-8-sig")
    log(f"\n✅ ¡Match completado! Archivo ÚNICO guardado en:\n   {archivo_salida}")


def procesar_unir_archivos(rutas_entrada, archivo_salida, log):
    log("Iniciando unión de múltiples archivos...")
    dfs = []
    
    for ruta in rutas_entrada:
        log(f"Leyendo archivo para unir: {os.path.basename(ruta)}")
        try:
            if ruta.lower().endswith('.csv'):
                try:
                    df_temp = pd.read_csv(ruta, dtype=str, encoding='utf-8')
                except UnicodeDecodeError:
                    df_temp = pd.read_csv(ruta, dtype=str, encoding='latin1')
            else:
                df_temp = pd.read_excel(ruta, dtype=str)
            
            # Estandarizamos los encabezados para que embonen correctamente
            df_temp.columns = df_temp.columns.str.strip().str.lower()
            dfs.append(df_temp)
        except Exception as e:
            raise ValueError(f"Error procesando el archivo {os.path.basename(ruta)}: {e}")

    # Concatenar todo
    df_base = pd.concat(dfs, ignore_index=True)
    log(f"\nTotal de filas unidas inicialmente: {len(df_base)}")

    # Intentar detectar la columna de correo para eliminar duplicados
    col_email = None
    for c in df_base.columns:
        if 'correo' in c or 'email' in c or 'correoelec' in c:
            col_email = c
            break

    if col_email:
        df_base[col_email] = df_base[col_email].fillna("").astype(str).str.strip().str.lower()
        antes = len(df_base)
        # Limpiar registros donde el correo viene completamente vacío
        df_base = df_base[df_base[col_email] != ""]
        # Eliminar los duplicados conservando el primero
        df_base = df_base.drop_duplicates(subset=[col_email], keep="first")
        log(f"Filas eliminadas (duplicados o correos vacíos) basadas en '{col_email}': {antes - len(df_base)}")
    else:
        log("⚠️ No se detectó ninguna columna de correo. No se eliminaron duplicados.")
        
    df_base.to_csv(archivo_salida, index=False, encoding="utf-8-sig")
    log(f"\n✅ ¡Archivos unidos con éxito! Guardado en:\n   {archivo_salida}")


# ══════════════════════ INTERFAZ GRÁFICA ══════════════════════════════

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Procesador de Contactos DENUE - Avanzado")
        self.resizable(False, False)
        self.configure(bg="#1e1e2e")
        self.archivos_in1 = []       
        self.archivos_base = []      
        self.archivos_externos = []  
        self.archivos_in3 = []
        self._build()

    def _build(self):
        PAD = dict(padx=14, pady=6)
        BG  = "#1e1e2e"
        FG  = "#cdd6f4"
        ACC = "#89b4fa"
        BTN = "#313244"
        FONT_H = ("Segoe UI", 11, "bold")
        FONT_N = ("Segoe UI", 10)

        tk.Label(self, text="Procesador de Contactos DENUE", bg=BG, fg=ACC, font=("Segoe UI", 14, "bold")).pack(pady=(18, 4))
        tk.Label(self, text="Exportación 100% en CSV (Multi-Archivo)", bg=BG, fg="#a6adc8", font=FONT_N).pack(pady=(0, 12))

        frm_radio = tk.LabelFrame(self, text=" ¿Qué deseas hacer? ", bg=BG, fg=ACC, font=FONT_H, padx=10, pady=5)
        frm_radio.pack(fill="x", **PAD)

        self.modo_var = tk.IntVar(value=1)
        tk.Radiobutton(frm_radio, text="1. Limpiar y Separar por Municipios (Max 5000 registros)", variable=self.modo_var, value=1, 
                       bg=BG, fg=FG, selectcolor=BTN, activebackground=BG, activeforeground=ACC, font=FONT_N, command=self._toggle_modo).pack(anchor="w")
        tk.Radiobutton(frm_radio, text="2. Cruzar datos (Match de múltiples bases y correos externos)", variable=self.modo_var, value=2, 
                       bg=BG, fg=FG, selectcolor=BTN, activebackground=BG, activeforeground=ACC, font=FONT_N, command=self._toggle_modo).pack(anchor="w")
        tk.Radiobutton(frm_radio, text="3. Unir varios archivos en uno solo (Eliminando duplicados)", variable=self.modo_var, value=3, 
                       bg=BG, fg=FG, selectcolor=BTN, activebackground=BG, activeforeground=ACC, font=FONT_N, command=self._toggle_modo).pack(anchor="w")

        self.frm_opcion1 = tk.Frame(self, bg=BG)
        self.frm_opcion2 = tk.Frame(self, bg=BG)
        self.frm_opcion3 = tk.Frame(self, bg=BG)

        # ----- UI OPCIÓN 1 -----
        f1_in = tk.Frame(self.frm_opcion1, bg=BG); f1_in.pack(fill="x", pady=4)
        tk.Label(f1_in, text="Archivo(s) Entrada:", bg=BG, fg=FG, font=FONT_N, width=22, anchor="w").pack(side="left")
        self.var_in1 = tk.StringVar(value="0 archivos agregados")
        tk.Entry(f1_in, textvariable=self.var_in1, width=38, bg=BTN, fg=FG, state="readonly", relief="flat", font=FONT_N).pack(side="left", padx=4)
        tk.Button(f1_in, text="➕ Agregar", command=self._buscar_in1, bg=ACC, fg="#1e1e2e", font=FONT_H, relief="flat", cursor="hand2", padx=4).pack(side="left")

        f1_out = tk.Frame(self.frm_opcion1, bg=BG); f1_out.pack(fill="x", pady=4)
        tk.Label(f1_out, text="Carpeta de Salida:", bg=BG, fg=FG, font=FONT_N, width=22, anchor="w").pack(side="left")
        self.var_out1 = tk.StringVar()
        tk.Entry(f1_out, textvariable=self.var_out1, width=38, bg=BTN, fg=FG, insertbackground=FG, relief="flat", font=FONT_N).pack(side="left", padx=4)
        tk.Button(f1_out, text="📁 Destino", command=self._buscar_out1, bg=ACC, fg="#1e1e2e", font=FONT_H, relief="flat", cursor="hand2", padx=4).pack(side="left")

        # ----- UI OPCIÓN 2 -----
        f2_base = tk.Frame(self.frm_opcion2, bg=BG); f2_base.pack(fill="x", pady=4)
        tk.Label(f2_base, text="Archivo(s) Base:", bg=BG, fg=FG, font=FONT_N, width=22, anchor="w").pack(side="left")
        self.var_base2 = tk.StringVar(value="0 bases agregadas")
        tk.Entry(f2_base, textvariable=self.var_base2, width=38, bg=BTN, fg=FG, state="readonly", relief="flat", font=FONT_N).pack(side="left", padx=4)
        tk.Button(f2_base, text="➕ Agregar", command=self._buscar_base2, bg=ACC, fg="#1e1e2e", font=FONT_H, relief="flat", cursor="hand2", padx=4).pack(side="left")

        f2_match = tk.Frame(self.frm_opcion2, bg=BG); f2_match.pack(fill="x", pady=4)
        tk.Label(f2_match, text="Archivos Match:", bg=BG, fg=FG, font=FONT_N, width=22, anchor="w").pack(side="left")
        self.var_match2 = tk.StringVar(value="0 archivos match agregados")
        tk.Entry(f2_match, textvariable=self.var_match2, width=38, bg=BTN, fg=FG, state="readonly", relief="flat", font=FONT_N).pack(side="left", padx=4)
        tk.Button(f2_match, text="➕ Agregar", command=self._buscar_match2, bg=ACC, fg="#1e1e2e", font=FONT_H, relief="flat", cursor="hand2", padx=4).pack(side="left")

        f2_out = tk.Frame(self.frm_opcion2, bg=BG); f2_out.pack(fill="x", pady=4)
        tk.Label(f2_out, text="CSV Final de Salida:", bg=BG, fg=FG, font=FONT_N, width=22, anchor="w").pack(side="left")
        self.var_out2 = tk.StringVar()
        tk.Entry(f2_out, textvariable=self.var_out2, width=38, bg=BTN, fg=FG, insertbackground=FG, relief="flat", font=FONT_N).pack(side="left", padx=4)
        tk.Button(f2_out, text="💾 Guardar", command=self._buscar_out2, bg=ACC, fg="#1e1e2e", font=FONT_H, relief="flat", cursor="hand2", padx=4).pack(side="left")

        # ----- UI OPCIÓN 3 -----
        f3_in = tk.Frame(self.frm_opcion3, bg=BG); f3_in.pack(fill="x", pady=4)
        tk.Label(f3_in, text="Archivos a Unir:", bg=BG, fg=FG, font=FONT_N, width=22, anchor="w").pack(side="left")
        self.var_in3 = tk.StringVar(value="0 archivos agregados")
        tk.Entry(f3_in, textvariable=self.var_in3, width=38, bg=BTN, fg=FG, state="readonly", relief="flat", font=FONT_N).pack(side="left", padx=4)
        tk.Button(f3_in, text="➕ Agregar", command=self._buscar_in3, bg=ACC, fg="#1e1e2e", font=FONT_H, relief="flat", cursor="hand2", padx=4).pack(side="left")

        f3_out = tk.Frame(self.frm_opcion3, bg=BG); f3_out.pack(fill="x", pady=4)
        tk.Label(f3_out, text="CSV Unido Salida:", bg=BG, fg=FG, font=FONT_N, width=22, anchor="w").pack(side="left")
        self.var_out3 = tk.StringVar()
        tk.Entry(f3_out, textvariable=self.var_out3, width=38, bg=BTN, fg=FG, insertbackground=FG, relief="flat", font=FONT_N).pack(side="left", padx=4)
        tk.Button(f3_out, text="💾 Guardar", command=self._buscar_out3, bg=ACC, fg="#1e1e2e", font=FONT_H, relief="flat", cursor="hand2", padx=4).pack(side="left")

        self.frm_opcion1.pack(fill="x", **PAD)

        # ── Botón procesar ──
        self.btn = tk.Button(self, text="▶  EJECUTAR TAREA", command=self._iniciar, bg="#a6e3a1", fg="#1e1e2e", font=("Segoe UI", 12, "bold"), relief="flat", cursor="hand2", padx=20, pady=6)
        self.btn.pack(pady=10)

        # ── Barra progreso y Log ──
        self.progress = ttk.Progressbar(self, mode="indeterminate", length=490)
        self.progress.pack(pady=(0,8))
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TProgressbar", troughcolor=BTN, background=ACC, thickness=6)

        frm_log = tk.Frame(self, bg=BG); frm_log.pack(fill="both", expand=True, padx=14, pady=(0,14))
        self.txt = tk.Text(frm_log, height=12, width=62, bg=BTN, fg=FG, font=("Consolas", 9), relief="flat", state="disabled", wrap="word")
        sb = tk.Scrollbar(frm_log, command=self.txt.yview, bg=BTN)
        self.txt.configure(yscrollcommand=sb.set)
        self.txt.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    def _toggle_modo(self):
        self.frm_opcion1.pack_forget()
        self.frm_opcion2.pack_forget()
        self.frm_opcion3.pack_forget()
        
        modo = self.modo_var.get()
        if modo == 1:
            self.frm_opcion1.pack(fill="x", padx=14, pady=6)
        elif modo == 2:
            self.frm_opcion2.pack(fill="x", padx=14, pady=6)
        else:
            self.frm_opcion3.pack(fill="x", padx=14, pady=6)

    def _log(self, msg):
        self.txt.configure(state="normal")
        self.txt.insert("end", msg + "\n")
        self.txt.see("end")
        self.txt.configure(state="disabled")

    # Búsquedas Modo 1
    def _buscar_in1(self):
        paths = filedialog.askopenfilenames(title="Selecciona archivo(s) Entrada (Excel/CSV)", filetypes=[("Archivos de Datos", "*.xlsx *.xls *.xlsm *.xlsb *.csv")])
        if paths:
            self.archivos_in1 = list(paths)
            self.var_in1.set(f"{len(paths)} archivo(s) listos")
            self.var_out1.set(os.path.join(os.path.dirname(paths[0]), "CSVs_Por_Municipio"))

    def _buscar_out1(self):
        path = filedialog.askdirectory(title="Carpeta destino para los CSVs")
        if path:
            self.var_out1.set(path)

    # Búsquedas Modo 2
    def _buscar_base2(self):
        paths = filedialog.askopenfilenames(title="Selecciona Archivo(s) Base (Excel/CSV)", filetypes=[("Archivos de Datos", "*.xlsx *.xls *.xlsm *.xlsb *.csv")])
        if paths:
            self.archivos_base = list(paths)
            self.var_base2.set(f"{len(paths)} archivo(s) base listo(s)")
            self.var_out2.set(os.path.join(os.path.dirname(paths[0]), "MATCH_FINAL_UNIFICADO.csv"))

    def _buscar_match2(self):
        paths = filedialog.askopenfilenames(title="Archivos Match para buscar correos (Excel/CSV)", filetypes=[("Excel/CSV", "*.xlsx *.xls *.csv")])
        if paths:
            self.archivos_externos = list(paths)
            self.var_match2.set(f"{len(paths)} archivo(s) match listo(s)")

    def _buscar_out2(self):
        path = filedialog.asksaveasfilename(title="Guardar CSV resultante", defaultextension=".csv", filetypes=[("Archivo CSV", "*.csv")])
        if path:
            self.var_out2.set(path)

    # Búsquedas Modo 3
    def _buscar_in3(self):
        paths = filedialog.askopenfilenames(title="Selecciona archivos a Unir (Excel/CSV)", filetypes=[("Archivos de Datos", "*.xlsx *.xls *.xlsm *.xlsb *.csv")])
        if paths:
            self.archivos_in3 = list(paths)
            self.var_in3.set(f"{len(paths)} archivo(s) listos")
            self.var_out3.set(os.path.join(os.path.dirname(paths[0]), "ARCHIVO_UNIDO.csv"))
            
    def _buscar_out3(self):
        path = filedialog.asksaveasfilename(title="Guardar CSV resultante", defaultextension=".csv", filetypes=[("Archivo CSV", "*.csv")])
        if path:
            self.var_out3.set(path)

    def _iniciar(self):
        modo = self.modo_var.get()
        
        if modo == 1:
            salida = self.var_out1.get().strip()
            if not self.archivos_in1 or not salida:
                messagebox.showwarning("Aviso", "Asegúrate de agregar al menos un archivo de entrada y seleccionar la carpeta de destino.")
                return
            target_func = lambda: procesar_separar_municipios(self.archivos_in1, salida, self._log)
            
        elif modo == 2:
            salida = self.var_out2.get().strip()
            if not self.archivos_base or not salida or not self.archivos_externos:
                messagebox.showwarning("Aviso", "Asegúrate de agregar al menos un archivo base, un archivo match y seleccionar el destino.")
                return
            target_func = lambda: procesar_match_correos(self.archivos_base, self.archivos_externos, salida, self._log)
            
        elif modo == 3:
            salida = self.var_out3.get().strip()
            if not self.archivos_in3 or not salida:
                messagebox.showwarning("Aviso", "Asegúrate de agregar los archivos a unir y seleccionar el destino.")
                return
            target_func = lambda: procesar_unir_archivos(self.archivos_in3, salida, self._log)

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