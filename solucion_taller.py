import os
import time
import random
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from enum import Enum
from typing import Tuple, List, Dict, Set, Optional
from IPython.display import display
import ipywidgets as widgets
import mesa

# Estilos de seaborn para gráficos estáticos
sns.set_theme(style="darkgrid")
plt.rcParams['font.size'] = 11

os.makedirs("images", exist_ok=True)

# ==========================================
# CLASES DE VISUALIZACIÓN INTERACTIVA (TABLERO Y OBJETOS)
# (Guía Notebook Robot_Aspiradora_IA)
# ==========================================

class Tablero:
    def __init__(self, tamano_celda=(50, 50), n_celdas=(5, 5)):
        self.out = widgets.HTML()
        display(self.out)
        self.tamano_celda = tamano_celda
        self.n_celdas = n_celdas

    def dibujar(self, objetos):
        tablero = "<table border='1' style='border-collapse: collapse; text-align: center; margin: 10px 0;'>{}</table>"
        filas = ""

        for i in range(self.n_celdas[0]):
            s = ""
            for j in range(self.n_celdas[1]):
                contenido = ""
                for o in objetos:
                    if o.x == j and o.y == i:
                        contenido += \
                        "<div style='display:inline-block; transform: rotate({angulo}deg); font-size:{tamano_emoticon}px; margin: 2px;'>{emoticon}</div>".\
                        format(angulo=o.angulo, tamano_emoticon=o.tamano_emoticon, emoticon=o.emoticon)
                s += "<td style='height:{alto}px; width:{ancho}px; vertical-align: middle;'>{contenido}</td>".\
                    format(alto=self.tamano_celda[0], ancho=self.tamano_celda[1], contenido=contenido)
            filas += "<tr>{}</tr>".format(s)
        tablero = tablero.format(filas)
        self.out.value = tablero


class ObjetoVisual:
    def __init__(self, x=0, y=0, angulo=0, emoticon="🤖", tamano_emoticon=30):
        self.x = x
        self.y = y
        self.angulo = angulo
        self.emoticon = emoticon
        self.tamano_emoticon = tamano_emoticon


# ==========================================
# ESTRUCTURAS BÁSICAS Y CLASES DE SIMULACIÓN
# ==========================================

class Action(Enum):
    AVANZAR = "avanzar"
    GIRAR_90 = "girar_90"
    GIRAR_180 = "girar_180"
    GIRAR_270 = "girar_270"
    ASPIRAR = "aspirar"
    NOOP = "noop"

class Orientation(Enum):
    NORTE = (0, -1, 0)   # (dx, dy, deg)
    ESTE = (1, 0, 90)
    SUR = (0, 1, 180)
    OESTE = (-1, 0, 270)

    @classmethod
    def get_orientation_by_deg(cls, deg: int):
        deg = deg % 360
        for o in cls:
            if o.value[2] == deg:
                return o
        return cls.NORTE

class Environment:
    def __init__(self, n: int = 5, m: int = 5, prob_hojas: float = 0.5, seed: Optional[int] = None):
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)
        self.n = n
        self.m = m
        self.grid = (np.random.rand(n, m) < prob_hojas).astype(int)
        self.hojas_iniciales = int(np.sum(self.grid))
    
    def tiene_hoja(self, pos: Tuple[int, int]) -> bool:
        x, y = pos
        return self.grid[x, y] == 1

    def limpiar_hoja(self, pos: Tuple[int, int]) -> bool:
        x, y = pos
        if self.grid[x, y] == 1:
            self.grid[x, y] = 0
            return True
        return False

    def es_valida(self, pos: Tuple[int, int]) -> bool:
        x, y = pos
        return 0 <= x < self.n and 0 <= y < self.m

    def hojas_restantes(self) -> int:
        return int(np.sum(self.grid))


class BaseAgent:
    def __init__(self, pos_inicial: Tuple[int, int], energia: int, orientacion_deg: int = 0):
        self.pos = pos_inicial
        self.orientacion = Orientation.get_orientation_by_deg(orientacion_deg)
        self.energia_inicial = energia
        self.energia = energia
        self.hojas_recogidas = 0
        self.movimientos = 0
        self.usos_sensor = 0

    def consumir_energia(self, cantidad: int = 1) -> bool:
        if self.energia >= cantidad:
            self.energia -= cantidad
            return True
        return False

    def girar(self, grados: int):
        if self.consumir_energia(1):
            nueva_deg = (self.orientacion.value[2] + grados) % 360
            self.orientacion = Orientation.get_orientation_by_deg(nueva_deg)
            self.movimientos += 1

    def avanzar(self, env: Environment) -> bool:
        if not self.consumir_energia(1):
            return False
        self.movimientos += 1
        dx, dy, _ = self.orientacion.value
        nueva_pos = (self.pos[0] + dx, self.pos[1] + dy)
        if env.es_valida(nueva_pos):
            self.pos = nueva_pos
            return True
        return False

    def aspirar(self, env: Environment) -> bool:
        if not self.consumir_energia(1):
            return False
        self.movimientos += 1
        if env.limpiar_hoja(self.pos):
            self.hojas_recogidas += 1
            return True
        return False

    def sensar_vecinos(self, env: Environment) -> Dict[str, Optional[bool]]:
        if not self.consumir_energia(1):
            return {}
        self.usos_sensor += 1
        x, y = self.pos
        vecinos = {
            'arriba': (x, y - 1),
            'abajo': (x, y + 1),
            'izquierda': (x - 1, y),
            'derecha': (x + 1, y)
        }
        res = {}
        for d, pos in vecinos.items():
            if env.es_valida(pos):
                res[d] = env.tiene_hoja(pos)
            else:
                res[d] = None
        return res


# ==========================================
# AGENTE REFLEXIVO SIMPLE
# ==========================================

class ReflexiveVacuumAgent(BaseAgent):
    def actuar(self, env: Environment) -> bool:
        if self.energia <= 0:
            return False

        if env.tiene_hoja(self.pos):
            self.aspirar(env)
            return True

        lectura = self.sensar_vecinos(env)
        if not lectura:
            return False

        direcciones_deg = {'arriba': 0, 'derecha': 90, 'abajo': 180, 'izquierda': 270}
        for d, tiene_hoja in lectura.items():
            if tiene_hoja:
                target_deg = direcciones_deg[d]
                diff_deg = (target_deg - self.orientacion.value[2]) % 360
                if diff_deg != 0:
                    self.girar(diff_deg)
                self.avanzar(env)
                return True

        dx, dy, _ = self.orientacion.value
        frente = (self.pos[0] + dx, self.pos[1] + dy)
        if env.es_valida(frente):
            self.avanzar(env)
        else:
            self.girar(90)
            self.avanzar(env)
        return True


# ==========================================
# AGENTE CON ESTADO INTERNO
# ==========================================

class StatefulVacuumAgent(BaseAgent):
    def __init__(self, pos_inicial: Tuple[int, int], energia: int, orientacion_deg: int = 0):
        super().__init__(pos_inicial, energia, orientacion_deg)
        self.casillas_visitadas: Set[Tuple[int, int]] = {pos_inicial}
        self.casillas_exploradas: Set[Tuple[int, int]] = set()
        self.hojas_conocidas: Set[Tuple[int, int]] = set()

    def actuar(self, env: Environment) -> bool:
        if self.energia <= 0:
            return False

        self.casillas_visitadas.add(self.pos)

        if env.tiene_hoja(self.pos):
            self.aspirar(env)
            self.hojas_conocidas.discard(self.pos)
            return True

        if self.hojas_conocidas:
            hoja_objetivo = min(self.hojas_conocidas, key=lambda p: abs(p[0] - self.pos[0]) + abs(p[1] - self.pos[1]))
            self._navegar_hacia(hoja_objetivo, env)
            return True

        if self.pos not in self.casillas_exploradas:
            lectura = self.sensar_vecinos(env)
            self.casillas_exploradas.add(self.pos)
            if lectura:
                direcciones_pos = {
                    'arriba': (self.pos[0], self.pos[1] - 1),
                    'abajo': (self.pos[0], self.pos[1] + 1),
                    'izquierda': (self.pos[0] - 1, self.pos[1]),
                    'derecha': (self.pos[0] + 1, self.pos[1])
                }
                for d, tiene_hoja in lectura.items():
                    if tiene_hoja:
                        self.hojas_conocidas.add(direcciones_pos[d])
            
            if self.hojas_conocidas:
                hoja_objetivo = min(self.hojas_conocidas, key=lambda p: abs(p[0] - self.pos[0]) + abs(p[1] - self.pos[1]))
                self._navegar_hacia(hoja_objetivo, env)
                return True

        vecinos_validos = []
        x, y = self.pos
        for dx, dy in [(0, -1), (1, 0), (0, 1), (-1, 0)]:
            p = (x + dx, y + dy)
            if env.es_valida(p):
                vecinos_validos.append(p)

        no_visitados = [p for p in vecinos_validos if p not in self.casillas_visitadas]
        if no_visitados:
            destino = random.choice(no_visitados)
            self._navegar_hacia(destino, env)
        else:
            destino = random.choice(vecinos_validos)
            self._navegar_hacia(destino, env)
        return True

    def _navegar_hacia(self, objetivo: Tuple[int, int], env: Environment):
        tx, ty = objetivo
        cx, cy = self.pos
        
        target_deg = None
        if tx > cx:
            target_deg = 90
        elif tx < cx:
            target_deg = 270
        elif ty > cy:
            target_deg = 180
        elif ty < cy:
            target_deg = 0

        if target_deg is not None:
            diff_deg = (target_deg - self.orientacion.value[2]) % 360
            if diff_deg != 0:
                self.girar(diff_deg)
            self.avanzar(env)


# ==========================================
# ANIMACIÓN INTERACTIVA EN JUPYTER / COLAB (ENERGÍA=40, DELAY=0.5 -> 20 SEGUNDOS)
# ==========================================

def animar_simulacion_interactiva(TipoAgente, n_grid=5, m_grid=5, energia=40, delay=0.5, seed=42):
    """
    Renderiza la animación del agente en el Tablero HTML dinámico.
    Por defecto ejecuta energia=40 pasos con delay=0.5s por paso para una duración total de ~20 segundos.
    """
    env = Environment(n_grid, m_grid, prob_hojas=0.5, seed=seed)
    agente = TipoAgente(pos_inicial=(0, 0), energia=energia, orientacion_deg=0)
    tablero = Tablero(tamano_celda=(50, 50), n_celdas=(n_grid, m_grid))

    def construir_objetos_visuales():
        objs = []
        objs.append(ObjetoVisual(x=agente.pos[0], y=agente.pos[1], angulo=agente.orientacion.value[2], emoticon="🤖", tamano_emoticon=28))
        for i in range(env.n):
            for j in range(env.m):
                if env.grid[i, j] == 1:
                    objs.append(ObjetoVisual(x=i, y=j, angulo=0, emoticon="🍂", tamano_emoticon=26))
        return objs

    tablero.dibujar(construir_objetos_visuales())
    time.sleep(delay)

    pasos = 0
    while agente.energia > 0 and env.hojas_restantes() > 0 and pasos < energia:
        actuado = agente.actuar(env)
        tablero.dibujar(construir_objetos_visuales())
        time.sleep(delay)
        if not actuado:
            break
        pasos += 1

    print(f"Simulación completa finalizada ({pasos * delay:.1f}s). Pasos ejecutados: {pasos}, Energía restante: {agente.energia}, Hojas recogidas: {agente.hojas_recogidas}/{env.hojas_iniciales}")


# ==========================================
# EXPERIMENTACIÓN MONTE CARLO (50 CORRIDAS)
# ==========================================

def ejecutar_experimentos(n_simulaciones: int = 50, n_grid: int = 5, m_grid: int = 5, energia_inicial: int = 40):
    resultados_reflexivo = []
    resultados_estado = []

    for seed in range(1000, 1000 + n_simulaciones):
        env_ref = Environment(n_grid, m_grid, prob_hojas=0.5, seed=seed)
        agente_ref = ReflexiveVacuumAgent(pos_inicial=(0, 0), energia=energia_inicial, orientacion_deg=0)
        
        pasos = 0
        while agente_ref.energia > 0 and env_ref.hojas_restantes() > 0 and pasos < 200:
            if not agente_ref.actuar(env_ref):
                break
            pasos += 1

        e_consumida_ref = energia_inicial - agente_ref.energia
        eficiencia_ref = agente_ref.hojas_recogidas / e_consumida_ref if e_consumida_ref > 0 else 0
        resultados_reflexivo.append({
            'sim_id': seed - 1000 + 1,
            'agente': 'Reflexivo Simple',
            'energia_inicial': energia_inicial,
            'energia_final': agente_ref.energia,
            'energia_consumida': e_consumida_ref,
            'hojas_iniciales': env_ref.hojas_iniciales,
            'hojas_recogidas': agente_ref.hojas_recogidas,
            'hojas_restantes': env_ref.hojas_restantes(),
            'movimientos': agente_ref.movimientos,
            'usos_sensor': agente_ref.usos_sensor,
            'eficiencia': eficiencia_ref
        })

        env_est = Environment(n_grid, m_grid, prob_hojas=0.5, seed=seed)
        agente_est = StatefulVacuumAgent(pos_inicial=(0, 0), energia=energia_inicial, orientacion_deg=0)

        pasos = 0
        while agente_est.energia > 0 and env_est.hojas_restantes() > 0 and pasos < 200:
            if not agente_est.actuar(env_est):
                break
            pasos += 1

        e_consumida_est = energia_inicial - agente_est.energia
        eficiencia_est = agente_est.hojas_recogidas / e_consumida_est if e_consumida_est > 0 else 0
        resultados_estado.append({
            'sim_id': seed - 1000 + 1,
            'agente': 'Con Estado Interno',
            'energia_inicial': energia_inicial,
            'energia_final': agente_est.energia,
            'energia_consumida': e_consumida_est,
            'hojas_iniciales': env_est.hojas_iniciales,
            'hojas_recogidas': agente_est.hojas_recogidas,
            'hojas_restantes': env_est.hojas_restantes(),
            'movimientos': agente_est.movimientos,
            'usos_sensor': agente_est.usos_sensor,
            'eficiencia': eficiencia_est
        })

    df_ref = pd.DataFrame(resultados_reflexivo)
    df_est = pd.DataFrame(resultados_estado)
    df_todos = pd.concat([df_ref, df_est], ignore_index=True)
    return df_ref, df_est, df_todos


# ==========================================
# MODELO MULTIAGENTE DE INFECCIÓN (MESA)
# ==========================================

class State(Enum):
    SUSCEPTIBLE = 0
    INFECTED = 1
    RECOVERED = 2

class InfectionAgent(mesa.Agent):
    def __init__(self, model, initial_state=State.SUSCEPTIBLE, p_movimiento=1.0):
        super().__init__(model)
        self.state = initial_state
        self.infection_time = 0
        self.p_movimiento = p_movimiento

    def step(self):
        if self.random.random() < self.p_movimiento:
            possible_steps = self.model.grid.get_neighborhood(
                self.pos, moore=True, include_center=False
            )
            new_position = self.random.choice(possible_steps)
            self.model.grid.move_agent(self, new_position)

        if self.state == State.INFECTED:
            self.infection_time += 1
            cellmates = self.model.grid.get_cell_list_contents([self.pos])
            for mate in cellmates:
                if mate.state == State.SUSCEPTIBLE:
                    if self.random.random() < self.model.p_contagio:
                        mate.state = State.INFECTED

            if self.infection_time >= self.model.t_infeccion:
                self.state = State.RECOVERED

class InfectionModel(mesa.Model):
    def __init__(self, N=100, width=15, height=15, p_contagio=0.35, t_infeccion=10, 
                 p_movimiento=1.0, infectados_iniciales=5, rng=None):
        super().__init__(rng=rng)
        self.num_agents = N
        self.grid = mesa.space.MultiGrid(width, height, True)
        self.p_contagio = p_contagio
        self.t_infeccion = t_infeccion

        for i in range(self.num_agents):
            initial_state = State.INFECTED if i < infectados_iniciales else State.SUSCEPTIBLE
            agent = InfectionAgent(self, initial_state=initial_state, p_movimiento=p_movimiento)
            
            x = self.random.randrange(self.grid.width)
            y = self.random.randrange(self.grid.height)
            self.grid.place_agent(agent, (x, y))

        self.datacollector = mesa.DataCollector(
            model_reporters={
                "Susceptibles": lambda m: sum(1 for a in m.agents if a.state == State.SUSCEPTIBLE),
                "Infectados": lambda m: sum(1 for a in m.agents if a.state == State.INFECTED),
                "Recuperados": lambda m: sum(1 for a in m.agents if a.state == State.RECOVERED)
            }
        )

    def step(self):
        self.datacollector.collect(self)
        self.agents.shuffle_do("step")


def simular_propagacion_infeccion(pasos: int = 50):
    model_base = InfectionModel(N=100, p_contagio=0.35, p_movimiento=1.0, rng=np.random.default_rng(42))
    for _ in range(pasos):
        model_base.step()
    df_base = model_base.datacollector.get_model_vars_dataframe()

    model_est1 = InfectionModel(N=100, p_contagio=0.35, p_movimiento=0.15, rng=np.random.default_rng(42))
    for _ in range(pasos):
        model_est1.step()
    df_est1 = model_est1.datacollector.get_model_vars_dataframe()

    model_est2 = InfectionModel(N=100, p_contagio=0.05, p_movimiento=1.0, rng=np.random.default_rng(42))
    for _ in range(pasos):
        model_est2.step()
    df_est2 = model_est2.datacollector.get_model_vars_dataframe()

    return df_base, df_est1, df_est2


def generar_graficos_y_guardar():
    df_ref, df_est, df_todos = ejecutar_experimentos(n_simulaciones=50)

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    sns.boxplot(data=df_todos, x='agente', y='hojas_recogidas', hue='agente', palette=['#e74c3c', '#2ecc71'], ax=axes[0], legend=False)
    axes[0].set_title('Hojas Recogidas por Agente')
    axes[0].set_xlabel('')
    axes[0].set_ylabel('Hojas')

    sns.boxplot(data=df_todos, x='agente', y='energia_consumida', hue='agente', palette=['#e74c3c', '#2ecc71'], ax=axes[1], legend=False)
    axes[1].set_title('Energía Consumida por Agente')
    axes[1].set_xlabel('')
    axes[1].set_ylabel('Energía (Unidades)')

    sns.barplot(data=df_todos, x='agente', y='eficiencia', hue='agente', palette=['#e74c3c', '#2ecc71'], ax=axes[2], errorbar=None, legend=False)
    axes[2].set_title('Eficiencia Promedio (Hojas / Energía)')
    axes[2].set_xlabel('')
    axes[2].set_ylabel('Eficiencia')

    plt.tight_layout()
    plt.savefig('images/comparativa_agentes.png', dpi=300)
    plt.close()

    df_base, df_est1, df_est2 = simular_propagacion_infeccion(pasos=50)
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    df_base[['Susceptibles', 'Infectados', 'Recuperados']].plot(ax=axes[0], color=['#3498db', '#e74c3c', '#2ecc71'], linewidth=2.5)
    axes[0].set_title('Sin Mitigación (Escenario Base)')
    axes[0].set_xlabel('Pasos de Simulación')
    axes[0].set_ylabel('Número de Agentes')

    df_est1[['Susceptibles', 'Infectados', 'Recuperados']].plot(ax=axes[1], color=['#3498db', '#e74c3c', '#2ecc71'], linewidth=2.5)
    axes[1].set_title('Estrategia 1: Aislamiento Social')
    axes[1].set_xlabel('Pasos de Simulación')

    df_est2[['Susceptibles', 'Infectados', 'Recuperados']].plot(ax=axes[2], color=['#3498db', '#e74c3c', '#2ecc71'], linewidth=2.5)
    axes[2].set_title('Estrategia 2: Uso de Mascarillas')
    axes[2].set_xlabel('Pasos de Simulación')

    plt.tight_layout()
    plt.savefig('images/infeccion_mesa.png', dpi=300)
    plt.close()
    print("Gráficos generados y guardados en la carpeta images/")


if __name__ == "__main__":
    print("Ejecutando simulaciones y generando gráficos en imágenes...")
    generar_graficos_y_guardar()
