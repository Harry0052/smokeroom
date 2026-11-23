# Noiseless oracle

Reference method: the closed form below, evaluated independently of the
package solver. Digits are recorded in `noiseless_steps.json`.

Units are µg/m³ and per hour. The step length is 1 hour. Outdoor
concentration is constant at 20 µg/m³. The initial indoor state at
2024-01-01T00:00:00+00:00 is 40 µg/m³.

```text
P = 0.8
a = 0.5 1/h
k_dep = 0.2 1/h
k_filt = 0 1/h on [00:00, 03:00) and 1.5 1/h on [03:00, 06:00)
L = a + k_dep + k_filt
C_ss = (P * a * C_out) / L
C(t + 1 h) = C_ss + (C(t) - C_ss) * exp(-L)
```

First step, filter off:

```text
L = 0.7 1/h
C_ss = (0.8 * 0.5 * 20) / 0.7 = 8 / 0.7 = 11.428571428571 µg/m³
exp(-0.7) = 0.496585303791
C(01:00) = 11.428571428571 + (40 - 11.428571428571) * 0.496585303791
         = 25.616722965469 µg/m³
```

The indoor column of `fixtures/noiseless/measurements.csv` is this
trajectory at each hour. A later solver matches it when it uses the
same declared parameters and does not adjust the state with the indoor
observations.
