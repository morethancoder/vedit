# Placement

Every layout decision the model used to make by hand.

Done when:
- [x] fit-in-shot: a text graphic's window stays inside one continuous shot (no cut, layout switch, full-screen scene); trims or shifts it and reports
- [x] side per cue from the face track over the whole window (margin 40 px, punch-in zoom applied); light/dark theme from measured frame brightness (cached)
- [x] busy backgrounds (screen layouts) get the feathered backdrop blur; unit tests cover side, theme and fit on synthetic face rows

## Refs

- port T `tools/build.py`: `face_at`, `faces_over`, `zoomed`, `hits_face`, `side_for`, `lum`, `brightness`, `theme_for`
