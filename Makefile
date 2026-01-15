# Makefile for stress testing pytest-uuid with parallel execution
# Usage: make -j4 stress-test  (runs 4 parallel pytest processes)

.PHONY: stress-test stress-test-8 run-stress

# Default number of xdist workers per pytest process
XDIST_WORKERS ?= 2

# Single stress test run (used as a dependency)
run-stress:
	uv run pytest tests/integration/test_stress_parallel.py \
		-n $(XDIST_WORKERS) \
		--dist loadscope \
		-q \
		--tb=short

# Create numbered targets that all depend on the same action
.PHONY: stress-1 stress-2 stress-3 stress-4 stress-5 stress-6 stress-7 stress-8
stress-1 stress-2 stress-3 stress-4 stress-5 stress-6 stress-7 stress-8:
	@echo "=== Stress test $@ starting ==="
	@uv run pytest tests/integration/test_stress_parallel.py \
		-n $(XDIST_WORKERS) \
		--dist loadscope \
		-q \
		--tb=short
	@echo "=== Stress test $@ completed ==="

# Run 4 parallel stress test processes (use with: make -j4 stress-test)
stress-test: stress-1 stress-2 stress-3 stress-4
	@echo ""
	@echo "All 4 parallel stress tests completed successfully!"

# Run 8 parallel stress test processes (more aggressive, use with: make -j8 stress-test-8)
stress-test-8: stress-1 stress-2 stress-3 stress-4 stress-5 stress-6 stress-7 stress-8
	@echo ""
	@echo "All 8 parallel stress tests completed successfully!"
