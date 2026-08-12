# Public release checklist

Use this checklist before switching `MilevskyYakov/Mnema` from private to public.

## Repository readiness

- [ ] `LICENSE` is present and intentional.
- [ ] `README.md` has a clear download link, platform boundary, and privacy warning.
- [ ] `SECURITY.md` tells users not to post private media, transcripts, secrets, or updater keys.
- [ ] GitHub issue templates include a privacy checklist.
- [ ] Repository description/topics are set for public discovery.
- [ ] Secret scan of tracked files and likely-sensitive history paths is clean.
- [ ] No tracked app outputs, private audio/video, transcripts, local app data, model files, or signing keys are present.

## Release readiness

- [ ] Latest GitHub Release has a signed macOS updater artifact.
- [ ] Latest GitHub Release has `latest.json` attached at the expected endpoint.
- [ ] `latest.json` points to the published artifact URL and includes the `.sig` contents.
- [ ] Public unauthenticated download of `latest.json` succeeds after the repository is public.
- [ ] Installed app can check updates against the public release endpoint.

## Manual smoke after making public

```bash
curl -L -f https://github.com/MilevskyYakov/Mnema/releases/latest/download/latest.json
```

Then open the installed app and use the “Обновление” card. Confirm that the app no longer shows the private-repo 404 state.
