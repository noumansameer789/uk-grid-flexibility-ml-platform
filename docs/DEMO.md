# Three-minute demonstration

The package includes a [28-second measured-data walkthrough](assets/gridflex-walkthrough.mp4), four figures in `assets/`, and a [recorded dashboard snapshot](demo-snapshot.html). The video illustrates the actual saved forecasts, optimiser output and measured evaluation; it is not a cloud-deployment recording. Recreate the video with `python scripts/render_demo.py` after installing the development dependencies and FFmpeg.

1. Start `gridflex serve` and open `http://localhost:8000`. Point out the **Historical replay** label and fixed horizon start. It was reconstructed later, not issued live on that date. It remains usable offline.
2. Show all five model rows and measured coverage. Explain why the seven-day mean beats LightGBM, why 86.3% misses 90%, and why the candidate remains unpromoted. Open **View forecast as a table** or download the CSV.
3. Keep a 60 kWh battery, 30% initial SOC, 80% target, 7 kW and 90% charging efficiency. Calculate the carbon plan. Compare it with immediate charging using exactly the same energy and power constraints.
4. Reduce available time to one hour. Show the infeasible-target response. The planner does not quietly lower the requested final charge.
5. Choose a cost objective and supply one tariff price per available half hour. Explain that prices are user inputs; there is no fabricated live tariff.
6. Select **Live forecast**. The API fetches real data, stamps retrieval time and persists the issued forecast. If the source fails, it returns an explicit error. Load weather context and explain why it is excluded from the current model backtest.
7. Open `/docs`, `/api/v1/model` and `/metrics`. Show the source manifest and MLflow run export in the repository.

The demonstration proves the software/data workflow. It does not prove commercial use, hardware control, actual emissions avoided, or an Azure deployment before that deployment has been activated and verified.
