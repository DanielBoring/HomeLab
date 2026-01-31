################ Parameters ################
    [CmdletBinding()]
    param(
        [string]$TenantID          = "", # Format: "xxxx-xxxx-xxxx-xxxx-xxxx"
        [string]$SubscriptionId    = "", # Format: "xxxx-xxxx-xxxx-xxxx-xxxx"
        [string]$ResourceGroup    = "rg-connectivity", # Name for your Resource Group
        [string]$Location         = "eastus2",           # Region location, use Programmatic Name from https://learn.microsoft.com/en-us/azure/reliability/regions-list
        [string]$VNetName         = "vnet-shared-eastus2-01", # Name for your Virtual Network
        [string]$VNetPrefix       = "10.0.48.0/22", # Address space for your Virtual Network
        [string]$GatewaySubnetPrefix = "10.0.51.224/27", # Basic SKU as small as a /29, for other SKUs must be /27 or larger
        [string]$GatewayName      = "vgw-prod-eastus2-01", # Name for your Virtual Network Gateway
        [string]$PublicIpName     = "pip-vgw-prod-eastus2-01", # Name for your Public IP
        [string]$GatewaySku       = "Basic"              
    )

################ Start of Script ################

# Check for Az module
    if (-not (Get-Module -ListAvailable -Name Az)) {
        Write-Error "Didn't find Az PowerShell module installed. Attempting to run installation."
        Install-Module -Name Az -Scope CurrentUser
        return
    } else {
        write-host 'Found Azure Az PowerShell module installed!' -ForegroundColor Green
        }
 
# Login to Azure
    $context = Get-AzContext
    if ($context) {
        Write-Host "Already connected to Azure as " -ForegroundColor Green -NoNewline
        Write-Host "$($context.Account.Id)" -ForegroundColor Cyan -NoNewline
        Write-Host " to subscription " -ForegroundColor Green -NoNewline
        Write-Host "$($context.Subscription.Name)" -ForegroundColor Cyan 
        if ($SubscriptionId -and $context.Subscription.Id -ne $SubscriptionId) {
            Write-Host "Switching to subscription: $SubscriptionId" -ForegroundColor Yellow
            Select-AzSubscription -SubscriptionId $SubscriptionId | Out-Null
            Update-AzConfig -DefaultSubscriptionForLogin $SubscriptionId -Scope Process | Out-Null
        }
    } else {
        Write-Host "Not connected to Azure. Connecting now..." -ForegroundColor Yellow
        Connect-AzAccount -TenantId $TenantID -ErrorAction Stop
        if ($SubscriptionId) { 
            Select-AzSubscription -SubscriptionId $SubscriptionId | Out-Null
            Update-AzConfig -DefaultSubscriptionForLogin $SubscriptionId -Scope Process | Out-Null
            $context = Get-AzContext
            Write-Host "Connected to Azure as " -ForegroundColor Green -NoNewline
            Write-Host "$($context.Account.Id)" -ForegroundColor Cyan -NoNewline
            Write-Host " to subscription " -ForegroundColor Green -NoNewline
            Write-Host "$($context.Subscription.Name)" -ForegroundColor Cyan 
        }
    }

# Create resource group if missing
    if (-not (Get-AzResourceGroup -Name $ResourceGroup -ErrorAction SilentlyContinue)) {
        Write-Host "Creating new Resource Group named '$ResourceGroup'." -ForegroundColor Green
        New-AzResourceGroup -Name $ResourceGroup -Location $Location | Out-Null
        
    } else {
        Write-Host "Existing Resource group named '$ResourceGroup' was found! Using that to proceed." -ForegroundColor Yellow
    }

# Check if Virtual Network exists, if not create it
    $vnet = Get-AzVirtualNetwork -Name $VNetName -ResourceGroupName $ResourceGroup -ErrorAction SilentlyContinue
    if (-not $vnet) {
        $vnet = New-AzVirtualNetwork -Name $VNetName -ResourceGroupName $ResourceGroup -Location $Location -AddressPrefix $VNetPrefix
    } else {
        Write-Host "Existing Virtual Network named '$VNetName' was found! Using that to proceed." -ForegroundColor Yellow
    }

# Check if GatewaySubnet exists, if not create it
# Note: Subnet name has to be "GatewaySubnet" and minimum /29 for Basic SKU
    $gwSubnet = $vnet.Subnets | Where-Object { $_.Name -eq "GatewaySubnet" }
    if (-not $gwSubnet) {
        Write-Host "GatewaySubnet not found. Attempting to create subnet in '$($vnet.Name)'. " -ForegroundColor Green
        $vnet | Add-AzVirtualNetworkSubnetConfig -Name "GatewaySubnet" -AddressPrefix $GatewaySubnetPrefix | Set-AzVirtualNetwork | Out-Null
        # refresh vnet object
        $vnet = Get-AzVirtualNetwork -Name $VNetName -ResourceGroupName $ResourceGroup
        Write-Host "Created "  -ForegroundColor Green -NoNewline
        Write-Host "$($vnet.Name)"  -ForegroundColor Cyan -NoNewline
        Write-Host " with address prefix of "  -ForegroundColor Green -NoNewline 
        $gwSubnet = $vnet.Subnets | Where-Object { $_.Name -eq "GatewaySubnet" }
        Write-host "$($gwSubnet.AddressPrefix)"  -ForegroundColor Cyan -NoNewline
        Write-Host "." -ForegroundColor Green  
    } else {
        Write-Host "Found "  -ForegroundColor Green -NoNewline
        Write-Host "$($gwSubnet.Name)"  -ForegroundColor Cyan -NoNewline
        Write-Host " already exists with address prefix of "  -ForegroundColor Green -NoNewline 
        Write-host "$($gwSubnet.AddressPrefix)"  -ForegroundColor Cyan -NoNewline
        Write-Host ". Using that to proceed." -ForegroundColor Green -NoNewline        
    }

# Create Public IP (Basic SKU for Basic gateway)
$pip = Get-AzPublicIpAddress -Name $PublicIpName -ResourceGroupName $ResourceGroup -ErrorAction SilentlyContinue
    if (-not $pip) {
        Write-Host "Creating Public IP named '$PublicIpName' for the Virtual Network Gateway." -ForegroundColor Green
        $pip = New-AzPublicIpAddress -Name $PublicIpName -ResourceGroupName $ResourceGroup -Location $Location -AllocationMethod Static -Sku Standard -Zone 1,2,3
    } else {
        Write-Host "Existing Public IP named '$PublicIpName' was found! Using that to proceed." -ForegroundColor Yellow
    }

# Gather some variables for the Virtual Network Gateway Deployment
    $subnetId = ($vnet.Subnets | Where-Object { $_.Name -eq "GatewaySubnet" }).Id
    $gwIpConfig = New-AzVirtualNetworkGatewayIpConfig -Name "gwipconfig" -SubnetId $subnetId -PublicIpAddressId $pip.Id

# Create the virtual network gateway (this is a long-running operation)
    $existingGw = Get-AzVirtualNetworkGateway -Name $GatewayName -ResourceGroupName $ResourceGroup -ErrorAction SilentlyContinue
    if ($existingGw) {
        Write-Host "Virtual Network Gateway '$GatewayName' already exists in resource group '$ResourceGroup'." -ForegroundColor Yellow
    } else {
        Write-Host "Creating Virtual Network Gateway (this can take 20+ minutes)..." -ForegroundColor Green
        New-AzVirtualNetworkGateway -Name $GatewayName `
            -ResourceGroupName $ResourceGroup `
            -Location $Location `
            -IpConfigurations $gwIpConfig `
            -GatewayType Vpn `
            -VpnType RouteBased `
            -GatewaySku $GatewaySku `
            -EnableBgp $false
        Write-Host 'Finished!' -ForegroundColor Green
        #Get-AzVirtualNetworkGateway -ResourceGroupName $ResourceGroup
    }