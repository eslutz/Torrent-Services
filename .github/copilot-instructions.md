# Authentication & API Usage

- **Always use API Keys**: When making requests to the API of *Arr services (Sonarr, Radarr, Prowlarr, etc.), ALWAYS include the `X-Api-Key` header. Do not rely on disabled authentication or session cookies for scripts.
- **Authentication Settings**: Setting `<AuthenticationMethod>` to `None` does not permanently disable authentication; the system will force user creation on the next UI access. Do not assume authentication can be permanently disabled to avoid using API keys.
