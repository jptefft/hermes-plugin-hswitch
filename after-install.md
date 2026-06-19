# hswitch installed

`hswitch` is installed. Restart Hermes CLI or the gateway before expecting `hermes hswitch ...` to appear in an already-running session.

Try:

```bash
hermes hswitch list
hermes hswitch doctor
hermes hswitch use 2
```

If you installed without `--enable`, enable it first:

```bash
hermes plugins enable hswitch
```

Standalone CLI users can run:

```bash
hswitch list
hswitch doctor
```
