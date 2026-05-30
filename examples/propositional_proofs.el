ALGORITHM propositional_proofs {

    // 1. A genuine tautology: modus ponens. Should be PROVEN.
    theorem modus_ponens: (P -> Q) /\ P -> Q;
    proof modus_ponens {
        QED;
    }

    // 2. NOT a tautology. The checker must REJECT this with a counterexample.
    theorem not_valid: P -> Q;
    proof not_valid {
        QED;
    }

    // 3. Proven from a hypothesis: assuming P and P->Q, conclude Q.
    theorem detachment: Q;
    proof detachment {
        hypothesis hp: P;
        hypothesis hpq: P -> Q;
        Q;
        QED;
    }

    // 4. Involves the realistic (uncertain) value -> UNCERTAIN, not proven.
    theorem maybe: P -> realistic;
    proof maybe {
        QED;
    }

    SHOW("proof checks complete");
}
