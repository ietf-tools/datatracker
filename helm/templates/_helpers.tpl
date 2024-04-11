{{/*
  Expand the name of the chart.
  */}}
{{- define "datatracker.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "datatracker.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create a fully qualified datatracker name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
*/}}
{{- define "datatracker.datatracker.fullname" -}}
{{- if .Values.datatracker.fullnameOverride -}}
{{- .Values.datatracker.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- printf "%s-%s" .Release.Name .Values.datatracker.name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s-%s" .Release.Name $name .Values.datatracker.name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Create a fully qualified celery name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
*/}}
{{- define "datatracker.celery.fullname" -}}
{{- if .Values.celery.fullnameOverride -}}
{{- .Values.celery.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- printf "%s-%s" .Release.Name .Values.celery.name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s-%s" .Release.Name $name .Values.celery.name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Create a fully qualified celery name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
*/}}
{{- define "datatracker.beat.fullname" -}}
{{- if .Values.beat.fullnameOverride -}}
{{- .Values.beat.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- printf "%s-%s" .Release.Name .Values.beat.name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s-%s" .Release.Name $name .Values.beat.name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Create a fully qualified rabbitmq name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
*/}}
{{- define "datatracker.rabbitmq.fullname" -}}
{{- if .Values.rabbitmq.fullnameOverride -}}
{{- .Values.rabbitmq.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- printf "%s-%s" .Release.Name .Values.rabbitmq.name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s-%s" .Release.Name $name .Values.rabbitmq.name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Create a fully qualified memcached name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
*/}}
{{- define "datatracker.memcached.fullname" -}}
{{- if .Values.memcached.fullnameOverride -}}
{{- .Values.memcached.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- printf "%s-%s" .Release.Name .Values.memcached.name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s-%s" .Release.Name $name .Values.memcached.name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "datatracker.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "datatracker.commonLabels" -}}
helm.sh/chart: {{ include "datatracker.chart" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/part-of: {{ include "datatracker.name" . | default "datatracker" }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "datatracker.selectorLabels" -}}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "datatracker.serviceAccountName.datatracker" -}}
{{- if .Values.serviceAccounts.datatracker.create -}}
  {{ default (include "datatracker.datatracker.fullname" .) .Values.serviceAccounts.datatracker.name }}
{{- else -}}
  {{ default "default" .Values.serviceAccounts.datatracker.name }}
{{- end -}}
{{- end }}

{{- define "datatracker.serviceAccountName.celery" -}}
{{- if .Values.serviceAccounts.celery.create -}}
  {{ default (include "datatracker.celery.fullname" .) .Values.serviceAccounts.celery.name }}
{{- else -}}
  {{ default "default" .Values.serviceAccounts.celery.name }}
{{- end -}}
{{- end }}

{{- define "datatracker.serviceAccountName.beat" -}}
{{- if .Values.serviceAccounts.beat.create -}}
  {{ default (include "datatracker.beat.fullname" .) .Values.serviceAccounts.beat.name }}
{{- else -}}
  {{ default "default" .Values.serviceAccounts.beat.name }}
{{- end -}}
{{- end }}

{{- define "datatracker.serviceAccountName.rabbitmq" -}}
{{- if .Values.serviceAccounts.rabbitmq.create -}}
  {{ default (include "datatracker.rabbitmq.fullname" .) .Values.serviceAccounts.rabbitmq.name }}
{{- else -}}
  {{ default "default" .Values.serviceAccounts.rabbitmq.name }}
{{- end -}}
{{- end }}

{{- define "datatracker.serviceAccountName.memcached" -}}
{{- if .Values.serviceAccounts.memcached.create -}}
  {{ default (include "datatracker.memcached.fullname" .) .Values.serviceAccounts.memcached.name }}
{{- else -}}
  {{ default "default" .Values.serviceAccounts.memcached.name }}
{{- end -}}
{{- end }}
