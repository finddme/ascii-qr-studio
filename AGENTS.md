# Development rules

- Run Python, dependencies, tests and browser tools only inside Docker. Never install project dependencies on the host.
- This is a general image + URL → ASCII art → static ASCII QR tool. Keep application-specific use cases out of tracked files.
- Store uploads, URLs, outputs, screenshots, research drafts, credentials and temporary files under ignored `dev/`. Never commit them or include them in Docker images.
- Use synthetic fixtures in tests. Never fetch the supplied destination URL.
- Verify the exact URL with an independent decoder. Digital validation does not guarantee camera or physical-output readability.
- Compare original, ASCII and QR at the same display size. Decoding success does not establish visual quality.
- Containers run unprivileged. CLI has no network; UI binds host loopback. Never mount the host home or Docker socket.
- Before pushing, run `./test.sh`, audit staged changes and ensure `git ls-files dev` is empty.
