/-
Formalization scaffold for the MatyOS-surfaced theorem

    radius(G) ≤ vertex_cover_number(G)   (connected G)

STATUS: the statement is formalized over mathlib's real `SimpleGraph.radius`
and a `vertexCoverNumber` defined here from mathlib's `SimpleGraph.IsVertexCover`.
The proof is NOT complete: it is reduced to the two obligations that the paper
proof (docs/conjectures/radius-le-vertex-cover.md) rests on, each left as `sorry`.

Why not complete here: mathlib currently lacks (a) a vertex-cover *number*,
(b) Jordan's tree-centre theorem `radius(T) = ⌈diam(T)/2⌉`, and (c) the
spanning-tree reduction lemmas in ready form. `radius` is also noncomputable, so
`decide` cannot discharge concrete instances. A faithful full formalization is a
multi-session project; this file pins exactly what remains.
-/
import Mathlib

open scoped Classical
open SimpleGraph

variable {V : Type*} [Fintype V]

namespace SimpleGraph

/-- The vertex cover number: the least cardinality of a vertex cover.
Defined from mathlib's `IsVertexCover`; `univ` is always a cover, so the set of
achievable cardinalities is nonempty and the infimum is attained. -/
noncomputable def vertexCoverNumber (G : SimpleGraph V) : ℕ :=
  sInf {n | ∃ c : Finset V, G.IsVertexCover (c : Set V) ∧ c.card = n}

/-- Obligation 1 (tree case). For a tree `T`, `radius(T) ≤ vertexCoverNumber(T)`.
Paper proof: Jordan's tree-centre theorem gives `radius(T) = ⌈diam T / 2⌉`, and a
diametral path on `diam+1` vertices forces `vertexCoverNumber(T) ≥ ⌊(diam+1)/2⌋ =
⌈diam/2⌉`. Both inputs are missing from mathlib. -/
theorem tree_radius_le_vertexCoverNumber
    (T : SimpleGraph V) (hT : T.IsTree) :
    T.radius ≤ (T.vertexCoverNumber : ℕ∞) := by
  sorry

/-- Obligation 2 (reduction). Passing to a spanning tree only grows the radius
(`edist_anti` / `radius` monotone under taking a subgraph) and shrinks the vertex
cover number (a cover of `G` covers any spanning subtree). mathlib has
`edist_anti`; the spanning-tree existence and the cover-number monotonicity still
need assembling. -/
theorem radius_le_vertexCoverNumber
    (G : SimpleGraph V) (hG : G.Connected) :
    G.radius ≤ (G.vertexCoverNumber : ℕ∞) := by
  -- take a spanning tree T ≤ G; then
  --   radius G ≤ radius T            (T ≤ G, edist_anti ⇒ radius monotone)
  --   radius T ≤ vertexCoverNumber T (Obligation 1)
  --   vertexCoverNumber T ≤ vertexCoverNumber G (a G-cover covers T)
  sorry

end SimpleGraph
