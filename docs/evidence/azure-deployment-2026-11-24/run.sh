#!/usr/bin/env bash
# GridFlex Azure run: evidence capture. Run inside the repository clone in Azure Cloud Shell (Bash).
# Usage: bash run.sh pre | tfvars <region> | plan | apply | http | job | share | restart | logs | lalogs |
#                    final | destroyplan | destroy | gone | cleanup | scan
# Each command's raw output is appended to a file under $E with a UTC time, the command line and its exit status.
# The subscription ID, tenant ID, signed-in account and shell user name are redacted on the way to disk.
set -uo pipefail

ROOT=$(git rev-parse --show-toplevel) || exit 1
E="$ROOT/docs/evidence/azure-deployment-${GF_DATE:-2026-11-24}"
TF="$ROOT/infra/terraform"
RG=gridflex-rg; APP=gridflex; JOB=gridflex-maintenance; WS=gridflex-logs; RULE=gridflex-failures; SHARE=gridflex-data
U=${USER:-}
IMAGE="ghcr.io/noumansameer789/uk-grid-flexibility-ml-platform@sha256:1f16c9cddcf62b422d8f82fea4e263676cc59398f0c0febb5ec9db2bad18230b"
mkdir -p "$E"

IFS='|' read -r SUB TEN WHO SUBNAME < <(az account show --query "join('|',[id,tenantId,user.name,name])" -o tsv)
[ "$SUBNAME" = "Azure for Students" ] || { echo "STOP: the active subscription is '$SUBNAME', not Azure for Students"; exit 3; }
[ ${#SUB} -eq 36 ] && [ ${#TEN} -eq 36 ] || { echo "STOP: could not read the subscription and tenant IDs"; exit 3; }

redact() {
  local a=(-e "s/$SUB/<subscription-ending-${SUB: -4}>/g" -e "s/$TEN/<tenant-ending-${TEN: -4}>/g")
  [ ${#WHO} -ge 4 ] && a+=(-e "s/$WHO/<owner-account>/g")
  [ ${#U} -ge 4 ] && a+=(-e "s/\b$U\b/<shell-user>/g")
  sed -u "${a[@]}"
}
now() { date -u +%Y-%m-%dT%H:%M:%SZ; }
run() {  # run <file> <command...>: append the UTC time, the command, its output and its exit status
  local out="$E/$1"; shift
  { echo "# UTC $(now)"; echo "# \$ $*"; "$@" 2>&1; echo "# exit $?"; echo; } | redact >> "$out"
}
say() { echo "$*" | redact | tee -a "$E/summary.txt"; }
dyn() { az config set extension.use_dynamic_install=yes_without_prompt >/dev/null 2>&1; }

image_check() {  # ask GHCR for the manifest of the pinned digest with an anonymous pull token
  local repo=${IMAGE#ghcr.io/} dig=${IMAGE#*@} tok
  repo=${repo%@*}
  tok=$(curl -fsS "https://ghcr.io/token?scope=repository:$repo:pull" | jq -r .token)
  { echo "# UTC $(now)"; echo "# anonymous pull token from ghcr.io, then HEAD of the manifest for $IMAGE"
    curl -sSI -H "Authorization: Bearer $tok" \
      -H "Accept: application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json" \
      "https://ghcr.io/v2/$repo/manifests/$dig" | tr -d '\r' | grep -iE "^HTTP|^content-type|^docker-content-digest|^content-length"
    echo; } >> "$E/preflight.txt"
  echo "image: $(grep -E '^HTTP' "$E/preflight.txt" | tail -1) digest_header_matches=$(grep -ci "docker-content-digest: $dig" "$E/preflight.txt")"
}

pre() {
  local f=preflight.txt ns
  : > "$E/$f"
  run $f git -C "$ROOT" log -1 --format='%H %cI %s'
  run $f az version --query '"azure-cli"' -o tsv
  run $f terraform version
  run $f az account show --query "{name:name,state:state,subscription:id,tenant:tenantId}" -o json
  run $f az policy assignment list --scope "/subscriptions/$SUB" --filter "atScope()" --query "[?displayName=='Allowed resource deployment regions'].{name:displayName,parameters:parameters}" --output json
  run $f az group exists --name $RG
  run $f az group list --query "[].name" -o tsv
  run $f az resource list --query "length(@)" -o tsv
  for ns in Microsoft.App Microsoft.OperationalInsights Microsoft.Storage Microsoft.Insights; do
    run $f az provider register --namespace $ns --wait --output none
    run $f az provider show --namespace $ns --query "{provider:namespace,state:registrationState}" --output json
  done
  run $f az consumption budget list --query "[].{name:name,amount:amount,timeGrain:timeGrain}" -o json
  image_check
  echo "--- every policy assignment that applies here (shown on screen only, not saved)"
  az policy assignment list --scope "/subscriptions/$SUB" --filter "atScope()" --query "[].[displayName,enforcementMode]" -o tsv
  echo "--- region policy parameters"
  az policy assignment list --scope "/subscriptions/$SUB" --filter "atScope()" --query "[?displayName=='Allowed resource deployment regions'].parameters" -o json | tr -d ' \n'; echo
  echo "--- providers: $(grep -c '"state": "Registered"' "$E/$f") of 4 Registered | exit codes not 0: $(grep -c '^# exit [^0]' "$E/$f")"
  grep -A6 'budget list' "$E/$f" | head -8
  say "preflight done $(now): subscription=$SUBNAME"
}

tfvars() {  # tfvars <region>: fill a private copy of the example variables file
  local loc=${1:?region} f="$TF/terraform.tfvars"
  ( umask 077; sed -e "s|YOUR_AZURE_SUBSCRIPTION_ID|$SUB|" -e "s|^container_image.*|container_image = \"$IMAGE\"|" \
      -e "s|^location .*|location        = \"$loc\"|" "$TF/terraform.tfvars.example" > "$f" )
  grep -v subscription_id "$f"
  echo "subscription line set: $(grep -c "subscription_id = \"$SUB\"" "$f")"
  git -C "$ROOT" check-ignore -q "infra/terraform/terraform.tfvars" && echo "terraform.tfvars is ignored by Git"
}

plan() {
  local f=terraform-plan.txt
  : > "$E/$f"
  cd "$TF" || exit 1
  run $f terraform init -lockfile=readonly -input=false -no-color
  run $f terraform fmt -check
  run $f terraform validate -no-color
  run $f terraform plan -input=false -no-color -out=deployment.tfplan
  run $f terraform show -no-color deployment.tfplan
  cd "$ROOT" || exit 1
  say "plan $(now): $(grep -E '^Plan:' "$E/$f" | sort -u | tr '\n' ' ')| commands returning 0: $(grep -c '^# exit 0' "$E/$f") of 5 | region: $(grep -m1 -E '^\s+\+ location ' "$E/$f" | tr -s ' ')"
  grep -E '^  # .* will be ' "$E/$f" | sort -u
}

apply() {
  local f=terraform-apply.txt
  : > "$E/$f"
  cd "$TF" || exit 1
  run $f terraform apply -input=false -no-color deployment.tfplan
  run $f terraform output -no-color
  cd "$ROOT" || exit 1
  say "apply $(now): $(grep -E '^(Apply complete|Error:)' "$E/$f" | head -3 | tr '\n' ' ')"
}

app_url() {
  if [ -n "${GF_URL:-}" ]; then URL="$GF_URL"; else URL=$(terraform -chdir="$TF" output -raw dashboard_url); fi
  echo "$URL" > "$E/app-url.txt"
}

req() {  # req <name> <method> <path> [json-body]: save the exact response body and one line of metadata
  local name=$1 method=$2 path=$3 body=${4:-} t0 res
  t0=$(now)
  local args=(-sS -o "$E/$name.json" -w '%{http_code} %{time_total}' --max-time 150 -X "$method")
  [ -n "$body" ] && args+=(-H 'Content-Type: application/json' -d "$body")
  res=$(curl "${args[@]}" "$URL$path" 2>"$E/$name.err") || true
  [ -s "$E/$name.err" ] || rm -f "$E/$name.err"
  [ -f "$E/$name.json" ] || : > "$E/$name.json"
  echo "utc_start=$t0 method=$method url=$URL$path http=${res%% *} seconds=${res##* } bytes=$(wc -c < "$E/$name.json") sha256=$(sha256sum "$E/$name.json" | cut -d' ' -f1)" > "$E/$name.meta.txt"
  HTTP=${res%% *}
}

wait_health() {  # the app scales from zero, so retry until /health answers 200
  local name=$1 i
  : > "$E/$name.attempts.txt"
  for i in $(seq 1 20); do
    req "$name" GET /health
    echo "attempt=$i $(cat "$E/$name.meta.txt")" >> "$E/$name.attempts.txt"
    [ "$HTTP" = "200" ] && return 0
    sleep 8
  done
  return 1
}

http() {
  app_url
  local card a b stable
  card=$(jq -r .model_sha256 "$ROOT/models/production/model_card.json")
  say "== HTTP gates started $(now) at $URL"

  wait_health gate-01-health
  say "G1 health: http=$HTTP attempts=$(wc -l < "$E/gate-01-health.attempts.txt") first_attempt_seconds=$(head -1 "$E/gate-01-health.attempts.txt" | grep -o 'seconds=[0-9.]*' | cut -d= -f2) body=$(cat "$E/gate-01-health.json")"

  req gate-02-ready GET /ready
  say "G2 ready: http=$HTTP status=$(jq -r .status "$E/gate-02-ready.json") sha_matches_model_card=$([ "$(jq -r .model_sha256 "$E/gate-02-ready.json")" = "$card" ] && echo true || echo false)"

  # Gate 9 runs before gate 3 on purpose: these are the first two live requests and they are sent together,
  # so both race to issue the forecast for the same origin.
  req gate-09-live-a GET '/api/v1/forecast?mode=live' &
  req gate-09-live-b GET '/api/v1/forecast?mode=live' &
  wait
  a=$(jq -r '.forecast_id // empty' "$E/gate-09-live-a.json" 2>/dev/null); b=$(jq -r '.forecast_id // empty' "$E/gate-09-live-b.json" 2>/dev/null)
  say "G9 simultaneous: a=[$(cut -d' ' -f1,4 "$E/gate-09-live-a.meta.txt")] b=[$(cut -d' ' -f1,4 "$E/gate-09-live-b.meta.txt")] same_nonempty_id=$([ -n "$a" ] && [ "$a" = "$b" ] && echo true || echo false) id=${a:0:16}"

  req gate-03-live GET '/api/v1/forecast?mode=live'
  say "G3 live: http=$HTTP slots=$(jq '.slots|length' "$E/gate-03-live.json" 2>/dev/null) mode=$(jq -r .mode "$E/gate-03-live.json" 2>/dev/null) origin=$(jq -r .origin "$E/gate-03-live.json" 2>/dev/null) issued_at=$(jq -r .issued_at "$E/gate-03-live.json" 2>/dev/null) id=$(jq -r .forecast_id "$E/gate-03-live.json" 2>/dev/null | cut -c1-16)"
  [ "$HTTP" = "200" ] || say "G3 live body: $(head -c 300 "$E/gate-03-live.json")"

  req gate-03-replay GET /api/v1/forecast
  say "G3 replay: http=$HTTP slots=$(jq '.slots|length' "$E/gate-03-replay.json" 2>/dev/null) mode=$(jq -r .mode "$E/gate-03-replay.json" 2>/dev/null)"

  req gate-04-schedule POST /api/v1/schedule '{}'
  say "G4 schedule: http=$HTTP objective=$(jq -r .objective "$E/gate-04-schedule.json" 2>/dev/null) slots=$(jq '.slots|length' "$E/gate-04-schedule.json" 2>/dev/null) reduction_pct=$(jq -r .estimated_carbon_reduction_pct "$E/gate-04-schedule.json" 2>/dev/null) forecast_mode=$(jq -r .forecast_mode "$E/gate-04-schedule.json" 2>/dev/null)"

  req gate-04-schedule-live POST /api/v1/schedule '{"mode":"live"}'
  say "G4 schedule on the live forecast: http=$HTTP slots=$(jq '.slots|length' "$E/gate-04-schedule-live.json" 2>/dev/null) reduction_pct=$(jq -r .estimated_carbon_reduction_pct "$E/gate-04-schedule-live.json" 2>/dev/null) forecast_mode=$(jq -r .forecast_mode "$E/gate-04-schedule-live.json" 2>/dev/null)"

  stable=$(az containerapp show -n $APP -g $RG --query properties.configuration.ingress.fqdn -o tsv 2>/dev/null)
  if [ -n "$stable" ]; then
    URL="https://$stable" req gate-01-health-app-fqdn GET /health
    say "G1 health on the app's own address https://$stable: http=$HTTP"
  fi
}

storage_env() {
  export AZURE_STORAGE_ACCOUNT; AZURE_STORAGE_ACCOUNT=$(az storage account list -g $RG --query "[0].name" -o tsv)
  export AZURE_STORAGE_KEY; AZURE_STORAGE_KEY=$(az storage account keys list -g $RG -n "$AZURE_STORAGE_ACCOUNT" --query "[0].value" -o tsv)
}

list_dir() {  # recursive listing: path, bytes, last modified (last modified is skipped under raw/ to keep it short)
  local p=$1 n t s lm full
  az storage file list --share-name $SHARE ${p:+--path "$p"} --query "[].[name,type,properties.contentLength]" -o tsv 2>/dev/null |
  while IFS=$'\t' read -r n t s; do
    full="${p:+$p/}$n"
    if [ "$t" = "dir" ]; then echo "$full/"; list_dir "$full"
    else
      lm=""; case "$full" in raw/*) ;; *) lm=$(az storage file show --share-name $SHARE --path "$full" --query properties.lastModified -o tsv 2>/dev/null);; esac
      echo "$full  ${s} bytes  $lm"
    fi
  done
}

share() {  # share [file]: list every file on the Azure Files share
  local f=${1:-gate-07-share.txt}
  storage_env
  { echo "# UTC $(now)"; echo "# recursive listing of file share $SHARE (path, bytes, last modified)"; list_dir ""; echo; } > "$E/$f"
  say "share listing $f at $(now): files=$(grep -c ' bytes' "$E/$f") issued=$(grep -c '^issued/.* bytes' "$E/$f") raw=$(grep -c '^raw/.* bytes' "$E/$f") duckdb=$(grep -c '^gridflex.duckdb ' "$E/$f") monitoring=$(grep -c '^processed/monitoring.json' "$E/$f")"
  grep -v '^raw/' "$E/$f" | head -30
}

job() {
  dyn
  local f=gate-06-job.txt st="" i
  : > "$E/$f"; : > "$E/gate-06-job-poll.txt"
  run $f az containerapp job start --name $JOB --resource-group $RG --query "{name:name}" -o json
  sleep 10
  EXE=$(az containerapp job execution list --name $JOB --resource-group $RG --query "sort_by([], &properties.startTime)[-1].name" -o tsv)
  say "G6 job execution $EXE started, seen at $(now)"
  for i in $(seq 1 70); do
    st=$(az containerapp job execution show --name $JOB --resource-group $RG --job-execution-name "$EXE" --query properties.status -o tsv 2>/dev/null)
    echo "$(now) status=$st" >> "$E/gate-06-job-poll.txt"
    case "$st" in Succeeded|Failed|Stopped|Degraded) break;; esac
    sleep 20
  done
  run $f az containerapp job execution show --name $JOB --resource-group $RG --job-execution-name "$EXE" --query "{name:name,status:properties.status,startTime:properties.startTime,endTime:properties.endTime}" -o json
  run $f timeout 90 az containerapp job logs show --name $JOB --resource-group $RG --execution "$EXE" --container maintenance --format text --tail 300
  storage_env
  rm -f "$E/gate-06-monitoring.json"
  az storage file download --share-name $SHARE --path processed/monitoring.json --dest "$E/gate-06-monitoring.json" --output none 2>"$E/gate-06-monitoring.err" || true
  [ -s "$E/gate-06-monitoring.err" ] || rm -f "$E/gate-06-monitoring.err"
  if [ -s "$E/gate-06-monitoring.json" ]; then
    say "G6 job: azure_status=$st execution_status=$(jq -r .execution_status "$E/gate-06-monitoring.json") report_status=$(jq -r .status "$E/gate-06-monitoring.json") freshness=$(jq -r .data_freshness.status "$E/gate-06-monitoring.json") issuance=$(jq -r .forecast_issuance.status "$E/gate-06-monitoring.json") weather=$(jq -r .weather_ingestion.status "$E/gate-06-monitoring.json") drift=$(jq -r .drift.status "$E/gate-06-monitoring.json") performance=$(jq -r .performance.status "$E/gate-06-monitoring.json") generated_at=$(jq -r .generated_at "$E/gate-06-monitoring.json")"
  else
    say "G6 job: azure_status=$st and processed/monitoring.json was not found on the share"
  fi
}

logs() {  # live log streams of the web app: platform events and container output
  dyn
  : > "$E/app-system-logs.txt"; : > "$E/app-console-logs.txt"
  run app-system-logs.txt timeout 90 az containerapp logs show -n $APP -g $RG --type system --tail 300 --format text
  run app-console-logs.txt timeout 90 az containerapp logs show -n $APP -g $RG --type console --tail 300 --format text
  echo "system rows=$(grep -vc '^#' "$E/app-system-logs.txt") console rows=$(grep -vc '^#' "$E/app-console-logs.txt")"
  grep -iE "probe|pull|start|fail|error|kill" "$E/app-system-logs.txt" | tail -n 14 | cut -c1-200
}

lalogs() {  # the same rows as Log Analytics returns them (ingestion can lag by several minutes)
  dyn
  local cid; cid=$(az monitor log-analytics workspace show -g $RG -n $WS --query customerId -o tsv)
  : > "$E/log-analytics-console.txt"; : > "$E/log-analytics-system.txt"
  run log-analytics-console.txt az monitor log-analytics query -w "$cid" --analytics-query "ContainerAppConsoleLogs_CL | where TimeGenerated > ago(6h) | project TimeGenerated, ContainerGroupName_s, ContainerName_s, Log_s | order by TimeGenerated asc | take 1500" -o tsv
  run log-analytics-system.txt az monitor log-analytics query -w "$cid" --analytics-query "ContainerAppSystemLogs_CL | where TimeGenerated > ago(6h) | project TimeGenerated, ContainerAppName_s, JobName_s, ReplicaName_s, Reason_s, Log_s | order by TimeGenerated asc | take 1500" -o tsv
  say "log analytics rows at $(now): console=$(grep -vc '^#' "$E/log-analytics-console.txt") system=$(grep -vc '^#' "$E/log-analytics-system.txt")"
  grep -c 'execution_status' "$E/log-analytics-console.txt"
}

restart() {
  app_url; dyn
  local f=gate-08-restart.txt rev before after mon
  : > "$E/$f"
  rev=$(az containerapp show -n $APP -g $RG --query properties.latestRevisionName -o tsv)
  wait_health gate-08-health-before
  req gate-08-live-before GET '/api/v1/forecast?mode=live'
  run $f az containerapp replica list -n $APP -g $RG --revision "$rev" --query "[].{replica:name,created:properties.createdTime}" -o json
  share gate-08-share-before.txt >/dev/null
  run $f az containerapp revision restart --name $APP --resource-group $RG --revision "$rev"
  sleep 60
  wait_health gate-08-health-after
  run $f az containerapp replica list -n $APP -g $RG --revision "$rev" --query "[].{replica:name,created:properties.createdTime}" -o json
  req gate-08-monitoring-after GET /api/v1/monitoring
  mon=$HTTP
  req gate-08-live-after GET '/api/v1/forecast?mode=live'
  share gate-08-share-after.txt >/dev/null
  before=$(jq -r '"\(.origin) \(.forecast_id[0:16])"' "$E/gate-08-live-before.json" 2>/dev/null); after=$(jq -r '"\(.origin) \(.forecast_id[0:16])"' "$E/gate-08-live-after.json" 2>/dev/null)
  say "G8 restart of $rev at $(now): health_after=$(cut -d' ' -f4 "$E/gate-08-health-after.meta.txt") attempts_after=$(wc -l < "$E/gate-08-health-after.attempts.txt") monitoring_after_http=$mon monitoring_status=$(jq -r .status "$E/gate-08-monitoring-after.json" 2>/dev/null) generated_at=$(jq -r .generated_at "$E/gate-08-monitoring-after.json" 2>/dev/null)"
  say "G8 forecast before: $before | after: $after | identical=$([ -n "$before" ] && [ "$before" = "$after" ] && echo true || echo false)"
  say "G8 files before=$(grep -c ' bytes' "$E/gate-08-share-before.txt") after=$(grep -c ' bytes' "$E/gate-08-share-after.txt") missing_after=$(comm -23 <(grep ' bytes' "$E/gate-08-share-before.txt" | cut -d' ' -f1 | sort) <(grep ' bytes' "$E/gate-08-share-after.txt" | cut -d' ' -f1 | sort) | wc -l)"
  grep -E '"replica"|"created"' "$E/$f" | tr -s ' ' | cut -c1-120
}

final() {
  dyn
  : > "$E/gate-10-alert-rule.txt"; : > "$E/inventory.txt"
  run gate-10-alert-rule.txt az resource show -g $RG -n $RULE --resource-type Microsoft.Insights/scheduledQueryRules --query "{name:name,enabled:properties.enabled,severity:properties.severity,evaluationFrequency:properties.evaluationFrequency,windowSize:properties.windowSize,actionGroups:properties.actions.actionGroups}" -o json
  run inventory.txt az resource list -g $RG --query "[].{name:name,type:type,location:location}" -o table
  run inventory.txt az containerapp show -n $APP -g $RG --query "{fqdn:properties.configuration.ingress.fqdn,latestRevision:properties.latestRevisionName,runningStatus:properties.runningStatus,image:properties.template.containers[0].image,cpu:properties.template.containers[0].resources.cpu,memory:properties.template.containers[0].resources.memory,minReplicas:properties.template.scale.minReplicas,maxReplicas:properties.template.scale.maxReplicas,location:location}" -o json
  run inventory.txt az containerapp job show -n $JOB -g $RG --query "{cron:properties.configuration.scheduleTriggerConfig.cronExpression,retryLimit:properties.configuration.replicaRetryLimit,timeout:properties.configuration.replicaTimeout,image:properties.template.containers[0].image,command:properties.template.containers[0].command}" -o json
  run inventory.txt az containerapp job execution list -n $JOB -g $RG --query "[].{name:name,status:properties.status,start:properties.startTime,end:properties.endTime}" -o table
  run inventory.txt az group list --query "[].name" -o tsv
  say "G10 alert rule at $(now): $(grep -E '"enabled"|"name"|"severity"' "$E/gate-10-alert-rule.txt" | tr -d ' \n')"
  say "inventory: $(grep -c 'Microsoft\.' "$E/inventory.txt") resources listed in $RG"
  cut -c1-150 "$E/inventory.txt" | grep -vE '^#|^$' | head -40
}

destroyplan() {
  local f=terraform-destroy.txt
  : > "$E/$f"
  cd "$TF" || exit 1
  run $f terraform plan -destroy -input=false -no-color
  cd "$ROOT" || exit 1
  say "destroy plan $(now): $(grep -E '^Plan:' "$E/$f" | tr '\n' ' ')"
}

destroy() {
  local f=terraform-destroy.txt
  cd "$TF" || exit 1
  run $f terraform destroy -auto-approve -input=false -no-color
  cd "$ROOT" || exit 1
  say "destroy $(now): $(grep -E '^(Destroy complete|Error:)' "$E/$f" | head -3 | tr '\n' ' ')"
}

gone() {
  : > "$E/teardown.txt"
  run teardown.txt az group exists --name $RG
  run teardown.txt az group list --query "[].name" -o tsv
  run teardown.txt az resource list --query "length(@)" -o tsv
  say "teardown check $(now): az group exists --name $RG -> $(grep -A2 'group exists' "$E/teardown.txt" | sed -n '2p') | resources left in the subscription: $(grep -A2 'resource list' "$E/teardown.txt" | sed -n '2p')"
}

cleanup() {  # remove local state, the saved plan, provider cache and the filled variables file
  rm -rf "$TF/.terraform" "$TF"/terraform.tfstate* "$TF/deployment.tfplan" "$TF/terraform.tfvars"
  ls -A "$TF"
  git -C "$ROOT" status --short | cut -c1-120 | head -20
}

scan() {  # look for identifiers and secrets in the evidence before it is committed
  local total=0 c p
  for p in "$SUB" "$TEN" "$WHO" "\b${U:-zzzzzzzz}\b" 'AccountKey' 'sig=' 'eyJ[A-Za-z0-9_-]{20}' 'gh[opsu]_[A-Za-z0-9]{20}' 'github_pat_' '[A-Za-z0-9+/]{86}==' '@exeter' '@gmail' 'access_key *= *"'; do
    c=$(grep -rIlE -- "$p" "$E" | wc -l); total=$((total + c))
    [ "$c" -gt 0 ] && { echo "FOUND pattern starting ${p:0:5} in:"; grep -rIlE -- "$p" "$E"; }
  done
  echo "scan: files with a match = $total; files checked = $(find "$E" -type f | wc -l)"
}

case "${1:-}" in
  pre|tfvars|plan|apply|http|job|share|restart|logs|lalogs|final|destroyplan|destroy|gone|cleanup|scan|image_check) "$@" ;;
  *) echo "usage: bash run.sh pre|tfvars <region>|plan|apply|http|job|share|restart|logs|lalogs|final|destroyplan|destroy|gone|cleanup|scan"; exit 2 ;;
esac
