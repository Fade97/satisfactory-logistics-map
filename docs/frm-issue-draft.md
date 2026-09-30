# Issue-Entwurf für porisius/FicsitRemoteMonitoring

**Titel:** Dedicated server: HTTP API returns "World not ready" (503) permanently after the daily session restart (ServerTravel)

**Version:** FRM 1.5.3 (LinuxServer), SML 3.12.0, Satisfactory Dedicated Server build 502094 (anniversary-2026), Linux (Pterodactyl/Wings)

### What happens
The dedicated server reloads the session every night ("Session Restart Timer elapsed, rebooting the session …" → `ProcessServerTravel`). The process keeps running. After that reload, every API call can fail permanently with

```
LogHttpServer: Warning: Blocked API call: World not ready.
LogHttpServer: Unknown Error getSessionInfo 503
```

until the whole server process is restarted. In our logs it worked after the reload on two nights and broke on the third (26.09.) and every night after that.

### Log evidence
```
[2026.09.26-00.00.00:033] LogGame: Display: Session Restart Timer elapsed, rebooting the session to maintain clock stability/game performance.
[2026.09.26-00.00.03:675] LogGameMode: ProcessServerTravel: /Game/FactoryGame/Map/GameLevel01/Persistent_Level?…loadgame=MySession_autosave_0_continue…
[2026.09.26-00.00.31:669] LogHttpServer: Warning: Blocked API call: World not ready.
[2026.09.26-00.00.52:666] LogHttpServer: Initializing WebSocket Service
[2026.09.26-00.00.52:666] LogHttpServer: Websocket Thread is already running. Stop start process.
[2026.09.26-00.00.54:520] LogSubsystemManager: Registered subsystem class '/FicsitRemoteMonitoring/Subsystems/FicsitRemoteMonitoringServer_BP…'
… from here on every request: "Blocked API call: World not ready." (13,877 times until 29.09.)
```

No `Stopping uWS listener` line appears during the travel.

### Probable cause (FicsitRemoteMonitoring.cpp)
- `StartWebSocketServer()` captures the world once inside the server thread: `auto World = GetWorld();` and passes that pointer to every `HandleApiRequest(World, …)`.
- `SocketRunning` is a file-level static (`bool SocketRunning = false;`), so it survives the actor. After ServerTravel the new `AFicsitRemoteMonitoring` actor calls `StartWebSocketServer(true)`, sees `SocketRunning == true` and returns ("already running"). The uWS thread keeps serving requests with the **old** `UWorld*`.
- `EndPlay()` → `StopWebSocketServer()` does not seem to run (or does not stop the uWS loop) during a seamless ServerTravel on the dedicated server. Also, `SocketRunning` is only reset after `app.run()` returns.
- `CallEndpoint` then checks `IsValid(WorldContext) || IsValid(WorldContext->GetWorld())`. The stale world pointer fails that check, sometimes only after GC has collected the old world. That would explain why it worked on some nights.

### Suggested fix
Resolve the world per request instead of capturing it at thread start. For example, keep a `TWeakObjectPtr` to the current actor that `BeginPlay` updates, or look up the current game world from `GEngine->GetWorldContexts()`. Alternatively, restart the uWS listener in `BeginPlay` when `SocketRunning` is already true.

### Workaround
A scheduled full process restart shortly after the session reload.
