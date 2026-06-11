# Definiciones

## Definición 1: Orden

Una orden es el conjunto de platillos que pueden conformar un menú.

**Notación:** Un platillo se representa como $p_i^j$, donde:
- $i$ es el tiempo (1, 2, 3, ...)
- $j$ es el índice del platillo dentro de ese tiempo

**Ejemplos:**

Si se piden $p_1^a$, $p_2^b$, $p_3^c$, la orden toma la forma:
```
(1_a, 2_b, 3_c)
```

Si se piden $p_2^d$, $p_3^e$, la orden toma la forma:
```
(2_d, 3_e)
```
Con esta representación el orden no importa ya que toda la información está contenida en los elementos de la orden:
```
(3_e, 2_d)
```

La cantidad de platillos que puede contener una orden está restringida por el menú de la cocina. Por ejemplo, si una cocina ofrece:

| Tiempo | Descripción | Platillos disponibles |
|--------|-------------|----------------------|
| 1 | Sopa | 3 |
| 2 | Arroz / Pasta / Ensalada | 4 |
| 3 | Plato fuerte | 6 |
| 4 | A la carta | 2 |
| 5 | Bebida | 5 |
| 6 | Postre | 2 |

En el desarrollo se ha usado un **menú de desarrollo** simplificado:

| Tiempo | Platillos disponibles |
|--------|----------------------|
| 1 | 2 |
| 2 | 2 |
| 3 | 2 |
| A la carta | 1 |
| Extra 1 | NA |

Por lo que una orden del **menú de desarrollo** puede tomar cualquiera de las siguientes formas:

```
(1) -> 1 platillo en total
(2) -> 1 platillo en total
(3) -> 1 platillo en total
(1, 2) -> 2 platillos en total
(1, 3) -> 2 platillos en total
(2, 3) -> 2 platillos en total
(1, 2, 3) -> 3 platillos en total
```
El tiempo **'A la carta'** es una **variante del tiempo 3** (por lo general tienen un costo mayor) por lo que las órdenes resultantes pueden tomar la forma con esta variante

```
(a_la_carta) -> 1 platillo en total
(1, a_la_carta) -> 2 platillo en total
(2, a_la_carta) -> 2 platillo en total
(1, 2, a_la_carta) -> 3 platillo en total
```
El tiempo Extra 1 tiene como único objetivo identificar las ordenes que estén compuestas de un único platillo generalmente como resultado de pedir más platos de los que pueden estar contendidos en un menú.

Por ejemplo, si hay una solicitud del tipo $p_1^a$, $p_2^b$, $p_2^a$, $p_3^c$, la orden toma la forma:
```
(1_a, 2_b, 2_a, 3_c)
```
Y por la naturaleza del negocio no ese esquema de orden no tiene esquema de cobro por lo que se transforma a
```
(1_a, 2_b, 3_c), (extra_2_a)
```
Sin embargo este esquema rompe con el concepto de comida corrida ya que como se puede observar que ese conjunto de platillos define 2 ordenes por lo que se vuelve necesaria la siguiente definición.

## Definición 2: Comanda

Una comanda es un lista de órdenes $ o_{1}, o_{2}, ...$. Esta definición extiende y generaliza la de orden ya que una orden estándar es una comanda con una orden. Si $o_{1}$ es una orden estándar $(1_{a}, 2_{b}, 3_{c})$, la respresentacion de la comanda es:
```
[o_1] = [(1_a, 2_a, 3_c)]
```
Entonces para el caso anterior queda resuelto el dilema del caso $p_1^a$, $p_2^b$, $p_2^a$, $p_3^c$:

```
[(1_a, 2_b, 2_a, 3_c)] -> [(1_a, 2_b, 3_c), (extra_2_a)]
```
Ya que toda orden pertenece a una comanda.

Estas definiciones nos aseguran la relación entre el pedido del cliente y la forma en que se representa el pedido en una comanda.

# Casos de uso
## 1.0 Un solo platillo suelto (un único tiempo)


## 2.0 Dos platillos

### 2.1 Tiempos iguales
<!-- TODO: completar -->

### 2.2 Tiempos distintos
<!-- TODO: completar -->

### 3.0 Tres platillos

#### 3.1 Tres platillos de tiempos iguales
<!-- TODO: completar -->

#### 3.2 Dos platillos de tiempos iguales + un platillo de tiempo distinto
*(caso 2.1 + caso 1.0)*
<!-- TODO: completar -->

#### 3.3 Tres platillos de tiempos distintos
<!-- TODO: completar -->
