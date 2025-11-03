# Contributing to DonationFlow CLI

Thank you for your interest in contributing!

## License and Contribution Terms

This repository is licensed under the **Business Source License 1.1 (BSL)**, which converts to the **Apache 2.0 License** on **2029-09-01**.

### Contributor License Agreement (CLA)

**All contributors must agree to our [Contributor License Agreement](cla.md) before we can merge your pull request.**

By submitting a pull request, you automatically agree to the CLA terms. Key points:

- ✅ You retain copyright in your contribution
- ✅ You grant the project owner rights to use your contribution under BSL 1.1
- ✅ Your contribution will convert to Apache 2.0 License on 2029-09-01 along with the rest of the codebase
- ✅ No separate signature required—your PR submission is your agreement

**Please review the [full CLA](cla.md) before submitting your first contribution.**

---

## Types of Contributions We Welcome

### Encouraged ✅
- **Bug reports** with clear reproduction steps
- **Bug fixes** for documented issues
- **Documentation improvements** and clarifications
- **Test coverage** improvements
- **Plugin examples** demonstrating custom business rules
- **Feature suggestions** via GitHub Issues (discuss before implementing)

### Requires Prior Discussion 💬
- **Major features** or architectural changes
- **New dependencies** or integrations
- **Breaking changes** to existing APIs

### Not Accepted ❌
- Contributions that introduce legal uncertainty
- Code copied from other projects without clear licensing
- Changes that conflict with the project's core design principles

---

## How to Contribute

1. **Open an issue first** for any non-trivial changes
2. **Fork the repository** and create a feature branch
3. **Follow existing code style** and conventions
4. **Add tests** for new functionality
5. **Update documentation** as needed
6. **Submit a pull request** with a clear description

### Pull Request Guidelines

- Use a descriptive branch name (e.g., `feature/add-stripe-integration`, `bugfix/fix-paypal-date-parsing`)
- Provide a clear and concise description of your changes
- Reference any related issues
- Ensure all tests pass before submitting

---

## Development Setup

To set up the project for development:

1. **Clone the repository:**

   ```bash
   git clone https://github.com/mkiiim/cdflow-cli.git
   cd cdflow-cli
   ```

2. **Create a virtual environment:**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install the package and dependencies in editable mode:**

   ```bash
   pip install -e .[dev]
   ```

   The `[dev]` extra will install development dependencies including `pytest`, `black`, and `flake8`.

4. **Run the tests:**

   ```bash
   pytest
   ```

---

## Code Style

Please follow the existing code style and conventions used in the project:

- **Formatting:** Use `black` for code formatting
- **Linting:** Use `flake8` for linting
- **Line length:** 100 characters maximum
- **Type hints:** Encouraged for new code
- **Docstrings:** Required for public functions and classes

Run these tools locally before submitting:

```bash
black .
flake8 .
```

---

## Code Review Process

- All PRs will be reviewed for technical merit and license compliance
- We may request changes or clarifications
- We reserve the right to decline PRs that don't align with project goals
- Accepted contributions will be merged with attribution

---

## Questions?

Open an issue or contact the maintainers before starting significant work.

---

**Note**: Because this is a BSL-licensed project (not open source until 2029-09-01), we maintain tighter control over contributions than typical MIT/Apache projects. This protects both contributors and the project's commercial viability.
