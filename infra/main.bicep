targetScope = 'resourceGroup'

@description('Azure region for the DCR. Use the same region as the Log Analytics workspace.')
param location string = resourceGroup().location

@description('Name of the existing Log Analytics workspace used by Sentinel.')
param workspaceName string

@description('Resource group containing the Log Analytics workspace.')
param workspaceResourceGroupName string = resourceGroup().name

@description('Subscription containing the Log Analytics workspace.')
param workspaceSubscriptionId string = subscription().subscriptionId

@description('Name of the direct-ingestion DCR.')
param dcrName string = 'sdp-cmdb-mvp-dcr'

@description('Custom Log Analytics table name. It must end with _CL.')
param tableName string = 'SDP_CMDB_Asset_CL'

@description('Custom stream name used by the collector.')
param streamName string = 'Custom-SDP_CMDB_Asset'

@description('Optional object ID of the identity that will call the Logs Ingestion API.')
param collectorPrincipalId string = ''

@allowed([
  'ServicePrincipal'
  'User'
  'Group'
  'ManagedIdentity'
])
@description('Principal type for the optional DCR role assignment.')
param collectorPrincipalType string = 'ServicePrincipal'

var workspaceResourceId = resourceId(
  workspaceSubscriptionId,
  workspaceResourceGroupName,
  'Microsoft.OperationalInsights/workspaces',
  workspaceName
)
var monitoringMetricsPublisherRoleDefinitionId = '3913510d-42f4-4e42-8a64-420c390055eb'

var assetColumns = [
  {
    name: 'TimeGenerated'
    type: 'datetime'
  }
  {
    name: 'RunId'
    type: 'string'
  }
  {
    name: 'CiId'
    type: 'string'
  }
  {
    name: 'CiType'
    type: 'string'
  }
  {
    name: 'CiName'
    type: 'string'
  }
  {
    name: 'Description'
    type: 'string'
  }
  {
    name: 'HostnameNorm'
    type: 'string'
  }
  {
    name: 'IpAddress'
    type: 'string'
  }
  {
    name: 'OsName'
    type: 'string'
  }
  {
    name: 'Site'
    type: 'string'
  }
  {
    name: 'Criticality'
    type: 'string'
  }
  {
    name: 'CiStatus'
    type: 'string'
  }
  {
    name: 'SourceCreatedTime'
    type: 'datetime'
  }
  {
    name: 'SourceLastUpdated'
    type: 'datetime'
  }
  {
    name: 'RowHash'
    type: 'string'
  }
  {
    name: 'RawAttributes'
    type: 'dynamic'
  }
]

resource workspace 'Microsoft.OperationalInsights/workspaces@2022-10-01' existing = {
  name: workspaceName
  scope: resourceGroup(workspaceSubscriptionId, workspaceResourceGroupName)
}

resource assetTable 'Microsoft.OperationalInsights/workspaces/tables@2022-10-01' = {
  parent: workspace
  name: tableName
  properties: {
    plan: 'Analytics'
    retentionInDays: 90
    schema: {
      name: tableName
      columns: assetColumns
    }
  }
}

resource dcr 'Microsoft.Insights/dataCollectionRules@2023-03-11' = {
  name: dcrName
  location: location
  kind: 'Direct'
  properties: {
    streamDeclarations: {
      '${streamName}': {
        columns: assetColumns
      }
    }
    destinations: {
      logAnalytics: [
        {
          name: 'sentinelWorkspace'
          workspaceResourceId: workspaceResourceId
        }
      ]
    }
    dataFlows: [
      {
        streams: [
          streamName
        ]
        destinations: [
          'sentinelWorkspace'
        ]
        transformKql: 'source'
        outputStream: 'Custom-${tableName}'
      }
    ]
  }
  dependsOn: [
    assetTable
  ]
}

resource dcrRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(collectorPrincipalId)) {
  name: guid(dcr.id, collectorPrincipalId, monitoringMetricsPublisherRoleDefinitionId)
  scope: dcr
  properties: {
    principalId: collectorPrincipalId
    principalType: collectorPrincipalType
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      monitoringMetricsPublisherRoleDefinitionId
    )
  }
}

output workspaceResourceId string = workspaceResourceId
output tableName string = tableName
output dcrName string = dcr.name
output dcrResourceId string = dcr.id
output streamName string = streamName

