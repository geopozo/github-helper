#!/usr/bin/env bash

if [ -z "$1" ]; then
  echo -e "\033[0;31m❌ Debes proporcionar el nombre del repositorio como argumento (ej: owner/reponame)\033[0m"
  exit 1
fi

REPO="$1"

total=0
success=0
fail=0

print_and_run() {
  echo -e "\n=============================="
  echo "$*"
  ((total++))
  if eval "$@"; then
    ((success++))
  else
    ((fail++))
    echo -e "\033[0;31m❌ Falló el commando:\033[0m"
    echo -e "\033[0;31m$*\033[0m"
  fi
}

run_basic_commands() {
  local base_cmd="uv run gh-helper"
  local cmds=("auth-status" "orgs" "user" "scopes" "repos")
  for cmd in "${cmds[@]}"; do
    print_and_run "$base_cmd $cmd"
  done

  local repo_cmds=(
    "tags -r $REPO"
    "project-configs -r $REPO"
    "releases -r $REPO"
    "pypi -r $REPO"
    "audit-releases -r $REPO"
    "audit-rulesets -r $REPO"
    "audit-versions -r $REPO"
  )

  for cmd in "${repo_cmds[@]}"; do
    print_and_run "$base_cmd $cmd"
  done
}

run_pretty_commands() {
  local base_cmd="uv run gh-helper --pretty"
  local cmds=("orgs" "user" "scopes" "repos")
  for cmd in "${cmds[@]}"; do
    print_and_run "$base_cmd $cmd"
  done

  local repo_cmds=(
    "tags -r $REPO"
    "project-configs -r $REPO"
    "releases -r $REPO"
    "pypi -r $REPO"
    "audit-releases -r $REPO"
    "audit-rulesets -r $REPO"
    "audit-versions -r $REPO"
  )

  for cmd in "${repo_cmds[@]}"; do
    print_and_run "$base_cmd $cmd"
  done
}

run_pretty_json_commands() {
  local base_cmd="uv run gh-helper --pretty --json"
  local cmds=("orgs" "user" "scopes" "repos")
  for cmd in "${cmds[@]}"; do
    print_and_run "$base_cmd $cmd"
  done

  local repo_cmds=(
    "tags -r $REPO"
    "project-configs -r $REPO"
    "releases -r $REPO"
    "pypi -r $REPO"
    "audit-releases -r $REPO"
    "audit-rulesets -r $REPO"
    "audit-versions -r $REPO"
  )

  for cmd in "${repo_cmds[@]}"; do
    print_and_run "$base_cmd $cmd"
  done
}

run_basic_commands
run_pretty_commands
run_pretty_json_commands

echo -e "\n=============================="
echo -e "Resumen de ejecución:"
printf "Total de commandos : %d\n" "$total"
printf "Commandos exitosos : \033[0;32m%d\033[0m\n" "$success"
printf "Commandos fallidos : \033[0;31m%d\033[0m\n" "$fail"
