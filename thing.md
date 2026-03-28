# How `version_2` Computes Damage and Resilience

This is the simplest way to think about the simulation:

## Big Idea

Each step does this:

1. Some countries are currently disrupted.
2. Those countries create trade pressure on the countries that import from them.
3. Importers try to resist that pressure using:
   - substitution
   - inventory
4. Whatever they cannot resist becomes shortage.
5. That shortage damages them.
6. The remaining damage can continue into the next step.

So the model is basically:

`disruption -> trade pressure -> resistance -> shortage -> damage -> next disruption`

---

# 1. The Main State Each Country Has

In [country_node.py](/Users/baiyangchen/Documents/Abel/UofT School /CSC111/csc111/assignments/CSC111-Project2/version_2/country_node.py), each country stores:

- `total_gdp`
- `total_imports`
- `total_exports`
- `current_health`
- `trading_partners`

The most important one during simulation is:

- `current_health`

Interpretation:
- `1.0` = fully healthy
- `0.8` = slightly damaged
- `0.4` = badly damaged
- `0.0` = collapsed in the model

---

# 2. How Trade Pressure Is Computed

This happens in [_compute_trade_pressures](/Users/baiyangchen/Documents/Abel/UofT School /CSC111/csc111/assignments/CSC111-Project2/version_2/simulation.py#L41).

For each disrupted exporter:

```python
pressure += disruption * edge_weight * trade_pressure_scale
```

## What each part means

- `disruption`
  - how badly the exporter is currently affected
- `edge_weight`
  - how dependent the importer is on that exporter
- `trade_pressure_scale`
  - global tuning constant

## Example

Suppose:

- USA disruption = `0.4`
- edge `USA -> CAN = 0.25`
- `trade_pressure_scale = 1.3`

Then Canada gets:

```python
0.4 * 0.25 * 1.3 = 0.13
```

So Canada receives `0.13` pressure from the USA.

If China also sends Canada pressure:

- CHN disruption = `0.3`
- edge `CHN -> CAN = 0.10`

Then extra pressure is:

```python
0.3 * 0.10 * 1.3 = 0.039
```

Total pressure on Canada:

```python
0.13 + 0.039 = 0.169
```

So countries can accumulate pressure from multiple disrupted partners.

---

# 3. How Countries Resist Pressure

This happens in [_apply_substitution_and_inventory](/Users/baiyangchen/Documents/Abel/UofT School /CSC111/csc111/assignments/CSC111-Project2/version_2/simulation.py#L61).

They resist in 2 ways:

- substitution
- inventory

## 3.1 Substitution

Substitution means:
- can this country replace lost imports from somewhere else?

The code computes an effective substitution rate:

```python
effective_substitution_rate = base_substitution_rate * (1.0 - pressure ** exponent)
```

This is important:
- if pressure is small, substitution works better
- if pressure is large, substitution works worse

So the model says:
- replacing 5% of imports is easier than replacing 40%

## Example

Suppose Canada has:
- base substitution rate = `0.5`
- pressure = `0.2`
- exponent = `0.75`

Then:

```python
effective_substitution_rate = 0.5 * (1 - 0.2 ** 0.75)
```

`0.2 ** 0.75` is about `0.299`

So:

```python
effective_substitution_rate ≈ 0.5 * (1 - 0.299)
                          ≈ 0.5 * 0.701
                          ≈ 0.3505
```

So effective substitution is about `0.35`.

Then shortage after substitution is:

```python
shortage_after_substitution = pressure * (1 - effective_substitution_rate)
                            = 0.2 * (1 - 0.3505)
                            = 0.2 * 0.6495
                            ≈ 0.1299
```

So substitution reduced pressure from `0.2` to about `0.13`.

---

## 3.2 Inventory

Now inventory absorbs some of what is left.

```python
inventory_used = min(current_inventory, shortage_after_substitution)
```

## Example

Suppose Canada has:
- inventory = `0.08`
- shortage after substitution = `0.1299`

Then:

```python
inventory_used = min(0.08, 0.1299) = 0.08
```

Remaining shortage:

```python
remaining_shortage = 0.1299 - 0.08 = 0.0499
```

So after substitution and inventory:
- original pressure = `0.2`
- final shortage = about `0.05`

That means Canada resisted most of the incoming pressure.

---

# 4. Immediate vs Deferred Shortage

The model does not always make all shortage hit immediately.

It splits leftover shortage into:
- immediate shortage
- deferred shortage

This is the code:

```python
deferred_amount = remaining_shortage * country_delay_share
immediate_amount = remaining_shortage - deferred_amount
```

## Example

Suppose:
- remaining shortage = `0.05`
- delay share = `0.4`

Then:

```python
deferred_amount = 0.05 * 0.4 = 0.02
immediate_amount = 0.05 - 0.02 = 0.03
```

So:
- `0.03` hurts this step
- `0.02` gets pushed into the next step

This makes the model less abrupt.

---

# 5. How Countries Take Damage

This happens in [_apply_health_updates](/Users/baiyangchen/Documents/Abel/UofT School /CSC111/csc111/assignments/CSC111-Project2/version_2/simulation.py#L104).

Damage comes from:
- current disruption
- current shortage

The formula is:

```python
total_damage = disruption * health_damage_scale + shortage * shortage_damage_scale
```

## Example

Suppose Germany has:
- disruption = `0.20`
- shortage = `0.05`
- `health_damage_scale = 0.75`
- `shortage_damage_scale = 0.2`

Then:

```python
total_damage = 0.20 * 0.75 + 0.05 * 0.2
             = 0.15 + 0.01
             = 0.16
```

So Germany takes `0.16` damage this step.

Then [apply_shock](/Users/baiyangchen/Documents/Abel/UofT School /CSC111/csc111/assignments/CSC111-Project2/version_2/country_node.py#L47) updates health multiplicatively:

```python
new_health = current_health * (1 - total_damage)
```

If Germany’s current health was `0.90`:

```python
new_health = 0.90 * (1 - 0.16)
           = 0.90 * 0.84
           = 0.756
```

So Germany falls from `0.90` to `0.756`.

---

# 6. How Inventory Rebuilds

This happens in [_rebuild_inventories](/Users/baiyangchen/Documents/Abel/UofT School /CSC111/csc111/assignments/CSC111-Project2/version_2/simulation.py#L131).

The code computes:

```python
rebuild_amount = inventory_rebuild_rate * health * (1 - max(disruption, pressure))
```

So inventory rebuild is bigger when:
- the country is healthier
- disruption is low
- pressure is low

## Example

Suppose:
- rebuild rate = `0.025`
- health = `0.8`
- disruption = `0.1`
- pressure = `0.2`

Then:

```python
rebuild_amount = 0.025 * 0.8 * (1 - 0.2)
               = 0.025 * 0.8 * 0.8
               = 0.016
```

So inventory goes up by `0.016`, capped at that country’s max inventory buffer.

---

# 7. How Next-Step Disruption Is Computed

This happens in [_compute_next_disruptions](/Users/baiyangchen/Documents/Abel/UofT School /CSC111/csc111/assignments/CSC111-Project2/version_2/simulation.py#L149).

The next disruption is mainly:

```python
next_impact = max(shortage, lingering_disruption, persistent_output_gap)
```

Right now:
- `persistent_output_gap` is basically turned off by default
- so the real competition is:
  - shortage
  - lingering disruption

Lingering disruption is:

```python
lingering_disruption = current_disruption * persistence
```

## Example

Suppose:
- current disruption = `0.20`
- persistence = `0.3`
- shortage = `0.05`

Then:

```python
lingering_disruption = 0.20 * 0.3 = 0.06
next_impact = max(0.05, 0.06) = 0.06
```

So next step disruption is `0.06`.

That means the country is still affected, even if the shortage was slightly smaller.

---

# 8. Full Mini Trace

Let’s do a full toy example.

Suppose:

- USA is initially shocked at `0.4`
- edge `USA -> CAN = 0.25`
- Canada has:
  - substitution rate = `0.5`
  - inventory = `0.08`
  - delay share = `0.4`
- current Canada health = `1.0`

## Step 0

### A. Pressure from USA
```python
pressure = 0.4 * 0.25 * 1.3 = 0.13
```

### B. Substitution
Assume effective substitution ends up around `0.32`

```python
shortage_after_substitution = 0.13 * (1 - 0.32)
                            = 0.13 * 0.68
                            = 0.0884
```

### C. Inventory
```python
inventory_used = min(0.08, 0.0884) = 0.08
remaining_shortage = 0.0884 - 0.08 = 0.0084
```

### D. Delay split
With delay share `0.4`:

```python
deferred = 0.0084 * 0.4 = 0.00336
immediate = 0.0084 - 0.00336 = 0.00504
```

### E. Damage
Suppose Canada had no current disruption yet, only shortage:

```python
damage = 0 * 0.75 + 0.00504 * 0.2
       = 0.001008
```

Health:

```python
new_health = 1.0 * (1 - 0.001008) = 0.998992
```

So Canada took only a tiny hit because it resisted most of the pressure.

### F. Next disruption
Suppose lingering disruption is `0`, shortage is `0.00504`:

```python
next_impact = 0.00504
```

If that is above threshold, Canada becomes disrupted next step.

---

# 9. Why Countries Have Different Buffering and Inventory

Because [build_country_resilience_profiles](/Users/baiyangchen/Documents/Abel/UofT School /CSC111/csc111/assignments/CSC111-Project2/version_2/graph_builder.py#L211) gives each country different values.

So two countries with the same incoming pressure can behave very differently.

## Example

Country A:
- diversified suppliers
- lower import dependence
- high substitution
- bigger inventory

Country B:
- concentrated suppliers
- high import dependence
- low substitution
- smaller inventory

If both get pressure `0.2`:

- Country A might reduce it to a shortage of `0.02`
- Country B might end up with a shortage of `0.12`

So the model is not just “same shock, same result for everyone.”

---

# 10. Simplest Formula Summary

For one country in one step:

## Incoming pressure
```python
sum(exporter_disruption * edge_weight * scale)
```

## Resistance
```python
pressure
-> substitution
-> inventory
-> split into immediate + deferred shortage
```

## Damage
```python
damage = disruption * health_damage_scale + shortage * shortage_damage_scale
```

## Next step
```python
next_disruption = max(shortage, lingering_disruption)
```

---

# 11. What To Remember

If you want the shortest useful interpretation:

- disruption spreads through import dependence
- countries resist with substitution and inventory
- unresolved shortage damages health
- countries do not all behave the same, because resilience is country-specific

If you want, I can next make:
1. a **diagram version**
2. a **report-ready markdown with headings**
3. a **line-by-line trace using one real country pair from your dataset**
