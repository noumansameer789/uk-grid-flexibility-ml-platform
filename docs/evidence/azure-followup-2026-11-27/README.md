# Azure follow-up, 27 November 2026 UTC

The [24 November run](../azure-deployment-2026-11-24/README.md) left two items outside the repository: the cost check and the gate 5 screenshot. Both are recorded here. Nothing was deployed or changed in Azure on 27 November.

Nouman Sameer owns the subscription and was signed in to the Azure portal. Claude (Anthropic, Fable 5.2) read the page in that browser session and wrote this record.

## Cost check

| Item | Observed at 15:45 UTC |
|---|---|
| Page | Cost Management → Cost analysis → Resource groups view |
| Scope | The owner's billing account, which is where the portal opened |
| Period | Nov 2026 |
| Total (GBP) | `<£0.01` |
| Average | `<£0.01` per day |
| Rows | 1 of 1 resource group: `gridflex-rg`, subscription Azure for Students, total `<£0.01` |
| Budget at this scope | None. The budget created on 24 November is on the subscription. |

The resources existed from 20:40 to 21:44 UTC on 24 November. Three days later the portal showed less than one penny for the month, all of it against `gridflex-rg`.

Limits of this check:

- The portal does not show amounts below one penny, so the exact figure is unknown.
- The values were read from the screen. No capture is kept, because the page shows the account name.
- The subscription-scope view and the credit balance were not read.
- Azure may still revise the month's cost data. This is the figure shown on 27 November.

## Gate 5 screenshot

[gate-05-dashboard-2026-11-24.jpg](gate-05-dashboard-2026-11-24.jpg) is the capture taken at gate 5 on 24 November at 21:12 UTC, while the app was running in Azure. The 24 November record describes it and kept it out of the repository.

It shows the forecast chart with the caption `Live data retrieved 24 Nov 2026 21:08 UK time` and the plan from the default inputs: 27.4% lower estimated carbon, 33.3 kWh, 3.21 kgCO₂ scheduled and 4.42 kgCO₂ for immediate charging. The plan values match the [page record](../azure-deployment-2026-11-24/gate-05-browser.txt).

The image is 800 by 455 pixels and has no address bar, so it does not show the address. The page record holds the address. The file is 34,360 bytes with SHA-256 `e87a24c17527bc979d693365d960c3a8b5bc2cfa30b42901dff412f9c234d8fb`. Its pixels are those of the original capture. It also carries a content credentials block, added when the session's file store delivered it to the PC.
