export class QuandleGenerator {
    static createTrivial(size) {
        const elements = Array.from({ length: size }, (_, i) => i);
        const operation_table = elements.map(x =>
            elements.map(y => x)
        );
        return { elements, operation_table };
    }

    static createDihedral(n) {
        const elements = Array.from({ length: n }, (_, i) => i);
        const operation_table = elements.map(x =>
            elements.map(y => {
                let res = (2 * y - x) % n;
                if (res < 0) res += n;
                return res;
            })
        );
        return { elements, operation_table };
    }

    static createConjugation(n = 3) {
        // Generate permutations of 0..n-1
        const perms = [];
        const indices = Array.from({ length: n }, (_, i) => i);

        function permute(arr, m = []) {
            if (arr.length === 0) {
                perms.push(m);
            } else {
                for (let i = 0; i < arr.length; i++) {
                    let curr = arr.slice();
                    let next = curr.splice(i, 1);
                    permute(curr.slice(), m.concat(next));
                }
            }
        }
        permute(indices);

        // Permutation multiply p1 * p2
        function multiply(p1, p2) {
            return p2.map(val => p1[val]);
        }

        // Permutation inverse
        function inverse(p) {
            const inv = new Array(p.length);
            for (let i = 0; i < p.length; i++) {
                inv[p[i]] = i;
            }
            return inv;
        }

        // Permutation key
        function toKey(p) {
            return p.join(',');
        }

        // Map permutation key to index
        const permToIndex = new Map();
        perms.forEach((p, i) => permToIndex.set(toKey(p), i));

        const size = perms.length;
        const elements = Array.from({ length: size }, (_, i) => i);

        // Operation: x |> y = y * x * y^-1
        const operation_table = [];
        for (let i = 0; i < size; i++) {
            const row = [];
            for (let j = 0; j < size; j++) {
                const x = perms[i];
                const y = perms[j];
                const y_inv = inverse(y);

                const res = multiply(multiply(y, x), y_inv);
                row.push(permToIndex.get(toKey(res)));
            }
            operation_table.push(row);
        }

        return { elements, operation_table };
    }

    static createAlexander(q, alpha) {
        // q is prime, alpha in F_q \ {0, 1}
        const elements = Array.from({ length: q }, (_, i) => i);
        const operation_table = elements.map(x =>
            elements.map(y => {
                // alpha*x + (1-alpha)*y (mod q)
                let term1 = alpha * x;
                let term2 = (1 - alpha) * y;
                let res = (term1 + term2) % q;
                if (res < 0) res += q;
                return res;
            })
        );
        return { elements, operation_table };
    }

    static createAlexanderF4(t_val) {
        // F4 = {0, 1, a, a+1}
        const elements = [0, 1, 2, 3];
        const labels = ["0", "1", "α", "α+1"];

        // Addition in F4 is XOR
        const add = (x, y) => x ^ y;

        const mulTable = [
            [0, 0, 0, 0],
            [0, 1, 2, 3],
            [0, 2, 3, 1],
            [0, 3, 1, 2]
        ];
        const mul = (x, y) => mulTable[x][y];

        const one_minus_t = add(1, t_val);

        const operation_table = elements.map(x =>
            elements.map(y => {
                // tx + (1-t)y
                const term1 = mul(t_val, x);
                const term2 = mul(one_minus_t, y);
                return add(term1, term2);
            })
        );

        return { elements, operation_table, elementLabels: labels };
    }

    static createAlexanderF8(t_val) {
        const elements = [0, 1, 2, 3, 4, 5, 6, 7];
        const labels = ["0", "1", "α", "α+1", "α^2", "α^2+1", "α^2+α", "α^2+α+1"];

        const add = (a, b) => a ^ b;

        const mul = (a, b) => {
            let p = 0;
            for (let i = 0; i < 3; i++) {
                if ((b >> i) & 1) {
                    p ^= (a << i);
                }
            }

            let res = 0;

            for (let i = 0; i <= 2; i++) {
                if ((a >> i) & 1) {
                    for (let j = 0; j <= 2; j++) {
                        if ((b >> j) & 1) {
                            res ^= (1 << (i + j));
                        }
                    }
                }
            }

            if ((res >> 4) & 1) {
                res ^= (1 << 4);
                res ^= 6;
            }

            if ((res >> 3) & 1) {
                res ^= (1 << 3);
                res ^= 3;
            }

            return res;
        };

        const one_minus_t = add(1, t_val);

        const operation_table = elements.map(x =>
            elements.map(y => {
                // tx + (1-t)y
                const term1 = mul(t_val, x);
                const term2 = mul(one_minus_t, y);
                return add(term1, term2);
            })
        );

        return { elements, operation_table, elementLabels: labels };
    }

    static createAlexanderZn_i(n, t_real, t_imag) {
        // Z_n[i] elements: a + bi
        const size = n * n;
        const elements = Array.from({ length: size }, (_, i) => i);

        const labels = elements.map(idx => {
            const b = Math.floor(idx / n);
            const a = idx % n;
            if (b === 0) return `${a}`;
            if (a === 0) return b === 1 ? "i" : `${b}i`;
            return `${a}+${b === 1 ? "" : b}i`;
        });

        // Addition in Z_n[i]
        const add = (u, v) => {
            const ua = u % n, ub = Math.floor(u / n);
            const va = v % n, vb = Math.floor(v / n);
            const ra = (ua + va) % n;
            const rb = (ub + vb) % n;
            return rb * n + ra;
        };

        const sub = (u, v) => {
            const ua = u % n, ub = Math.floor(u / n);
            const va = v % n, vb = Math.floor(v / n);
            let ra = (ua - va) % n; if (ra < 0) ra += n;
            let rb = (ub - vb) % n; if (rb < 0) rb += n;
            return rb * n + ra;
        };

        // Multiplication in Z_n[i] with i^2 = -1
        const mul = (u, v) => {
            const a = u % n, b = Math.floor(u / n);
            const c = v % n, d = Math.floor(v / n);

            let real = (a * c - b * d) % n;
            if (real < 0) real += n;

            let imag = (a * d + b * c) % n;

            return imag * n + real;
        };

        const t_idx = t_imag * n + t_real;

        const one_idx = 1;
        const one_minus_t = sub(one_idx, t_idx);

        const operation_table = elements.map(x =>
            elements.map(y => {
                // tx + (1-t)y
                const term1 = mul(t_idx, x);
                const term2 = mul(one_minus_t, y);
                return add(term1, term2);
            })
        );

        return { elements, operation_table, elementLabels: labels };
    }
}
