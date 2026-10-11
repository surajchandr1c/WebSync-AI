"""Sample computational workload computing primes to demonstrate authentic CPU execution."""

import time


def calculate_primes(limit: int = 50000) -> int:
    sieve = [True] * limit
    sieve[0] = sieve[1] = False
    for i in range(2, int(limit**0.5) + 1):
        if sieve[i]:
            for j in range(i * i, limit, i):
                sieve[j] = False
    return sum(sieve)


if __name__ == "__main__":
    start = time.perf_counter()
    count = calculate_primes(50000)
    elapsed = time.perf_counter() - start
    print(f"Calculated {count} primes up to 50,000 in {elapsed:.4f} seconds.")
