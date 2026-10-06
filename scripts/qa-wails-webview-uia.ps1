param(
    [ValidateSet('Windows', 'TreeSummary', 'Restore', 'CloseWindow', 'Snapshot', 'ListOptions', 'Fingerprint', 'FindText', 'ReadStatus', 'ReadCapacity', 'ReadFindings', 'ReadPlanState', 'ReadDeploymentTargets', 'ReadPlanTail', 'ReadRunEvents', 'ReadServerTail', 'ReadSensitivePresence', 'ReadValue', 'ReadSelectedOption', 'ReadToggle', 'Invoke', 'ConfirmPreparation', 'Select', 'SelectTab', 'AddSelection', 'Expand', 'ChooseOption', 'ChooseOptionByKeyboard', 'Toggle', 'Focus', 'ScrollIntoView', 'SetText', 'TypeText')]
    [string]$Action = 'Snapshot',
    [string]$WindowTitle = 'Platform Installer',
    [string]$Name = '',
    [string]$OptionName = '',
    [ValidateRange(0, 32)]
    [int]$OptionIndex = 0,
    [string]$InputEnvVar = '',
    [ValidateRange(0, 100)]
    [int]$Ordinal = 0
)

# QA-only UI Automation of the actual Wails WebView2 window. This script does
# not call Wails bindings, evaluate JavaScript, read DOM values, or launch Core.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

$expectedExe = [System.IO.Path]::GetFullPath(
    [System.IO.Path]::Combine($PSScriptRoot, '..', 'build', 'bin', 'platform-installer-ui.exe')
)
$processes = @(Get-Process -Name 'platform-installer-ui' -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -eq $expectedExe })
if ($processes.Count -ne 1) {
    throw 'QA_WEBVIEW_PROCESS_NOT_UNIQUE'
}
$processId = $processes[0].Id
$condition = [System.Windows.Automation.PropertyCondition]::new(
    [System.Windows.Automation.AutomationElement]::ProcessIdProperty, $processId
)
$windows = [System.Windows.Automation.AutomationElement]::RootElement.FindAll(
    [System.Windows.Automation.TreeScope]::Children, $condition
)
$candidates = @(
    for ($i = 0; $i -lt $windows.Count; $i++) {
        $window = $windows.Item($i)
        if ($window.Current.ControlType -eq [System.Windows.Automation.ControlType]::Window) {
            $window
            $owned = $window.FindAll(
                [System.Windows.Automation.TreeScope]::Descendants,
                [System.Windows.Automation.PropertyCondition]::new(
                    [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
                    [System.Windows.Automation.ControlType]::Window
                )
            )
            for ($j = 0; $j -lt $owned.Count; $j++) {
                $child = $owned.Item($j)
                if ($child.Current.ProcessId -eq $processId) { $child }
            }
        }
    }
)
if ($Action -eq 'Windows') {
    @($candidates | ForEach-Object {
        [pscustomobject]@{ title = $_.Current.Name; processId = $processId }
    }) | ConvertTo-Json -Compress
    return
}

$matchingWindows = @($candidates | Where-Object { $_.Current.Name -eq $WindowTitle })
if ($matchingWindows.Count -ne 1) {
    throw 'QA_WEBVIEW_WINDOW_NOT_UNIQUE'
}
if ($Action -in @('Restore', 'CloseWindow', 'Invoke', 'ConfirmPreparation', 'Select', 'SelectTab', 'AddSelection', 'Expand', 'ChooseOption', 'ChooseOptionByKeyboard', 'Toggle', 'Focus', 'ScrollIntoView', 'SetText', 'TypeText')) {
    [System.Media.SystemSounds]::Question.Play()
    try { [Console]::Beep(587, 140) } catch { }
    Start-Sleep -Seconds 3
}
$root = $matchingWindows[0]
if ($Action -eq 'ConfirmPreparation') {
    $dialogs = $root.FindAll(
        [System.Windows.Automation.TreeScope]::Descendants,
        [System.Windows.Automation.PropertyCondition]::new(
            [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
            [System.Windows.Automation.ControlType]::Window
        )
    )
    $matches = @(
        for ($i = 0; $i -lt $dialogs.Count; $i++) {
            if ($dialogs.Item($i).Current.Name -eq 'Сообщение с wails.localhost:') {
                $dialogs.Item($i)
            }
        }
    )
    if ($matches.Count -ne 1) { throw 'QA_WEBVIEW_PREPARATION_CONFIRMATION_NOT_UNIQUE' }
    $dialog = $matches[0]
    $texts = $dialog.FindAll(
        [System.Windows.Automation.TreeScope]::Descendants,
        [System.Windows.Automation.PropertyCondition]::new(
            [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
            [System.Windows.Automation.ControlType]::Text
        )
    )
    $prompt = @(
        for ($i = 0; $i -lt $texts.Count; $i++) {
            if ($texts.Item($i).Current.Name -eq 'Подготовить выбранный узел выполнения? Это может активировать проверенное окружение.') {
                $texts.Item($i)
            }
        }
    )
    if ($prompt.Count -ne 1) { throw 'QA_WEBVIEW_PREPARATION_CONFIRMATION_TEXT_MISMATCH' }
    $buttons = $dialog.FindAll(
        [System.Windows.Automation.TreeScope]::Descendants,
        [System.Windows.Automation.PropertyCondition]::new(
            [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
            [System.Windows.Automation.ControlType]::Button
        )
    )
    $ok = @(
        for ($i = 0; $i -lt $buttons.Count; $i++) {
            if ($buttons.Item($i).Current.Name -eq 'ОК') { $buttons.Item($i) }
        }
    )
    if ($ok.Count -ne 1) { throw 'QA_WEBVIEW_PREPARATION_CONFIRM_BUTTON_NOT_UNIQUE' }
    $invoke = $null
    if (-not $ok[0].TryGetCurrentPattern(
        [System.Windows.Automation.InvokePattern]::Pattern, [ref]$invoke
    )) { throw 'QA_WEBVIEW_PREPARATION_CONFIRM_INVOKE_UNAVAILABLE' }
    $invoke.Invoke()
    [pscustomobject]@{ action = 'ConfirmPreparation'; completed = $true } | ConvertTo-Json -Compress
    return
}
if ($Action -eq 'CloseWindow') {
    $windowPattern = $null
    if (-not $root.TryGetCurrentPattern([System.Windows.Automation.WindowPattern]::Pattern,
        [ref]$windowPattern)) { throw 'QA_WEBVIEW_WINDOW_PATTERN_UNAVAILABLE' }
    $windowPattern.Close()
    [pscustomobject]@{ action = 'CloseWindow'; completed = $true } | ConvertTo-Json -Compress
    return
}
if ($Action -eq 'Restore') {
    $windowPattern = $null
    if (-not $root.TryGetCurrentPattern([System.Windows.Automation.WindowPattern]::Pattern,
        [ref]$windowPattern)) { throw 'QA_WEBVIEW_WINDOW_PATTERN_UNAVAILABLE' }
    $windowPattern.SetWindowVisualState([System.Windows.Automation.WindowVisualState]::Normal)
    [pscustomobject]@{ action = 'Restore'; completed = $true } | ConvertTo-Json -Compress
    return
}
if ($Action -eq 'TreeSummary') {
	$windowPattern = $null
	$windowState = 'UNAVAILABLE'
	if ($root.TryGetCurrentPattern([System.Windows.Automation.WindowPattern]::Pattern,
	    [ref]$windowPattern)) { $windowState = $windowPattern.Current.WindowVisualState.ToString() }
    $children = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants,
        [System.Windows.Automation.Condition]::TrueCondition)
    $types = @{}
    for ($i = 0; $i -lt $children.Count; $i++) {
        $type = $children.Item($i).Current.ControlType.ProgrammaticName
        if (-not $types.ContainsKey($type)) { $types[$type] = 0 }
        $types[$type]++
    }
    [pscustomobject]@{ count = $children.Count; types = $types; windowState = $windowState; offscreen = $root.Current.IsOffscreen } | ConvertTo-Json -Compress
    return
}
if ($WindowTitle -eq 'Platform Installer') {
    $documents = $root.FindAll(
        [System.Windows.Automation.TreeScope]::Descendants,
        [System.Windows.Automation.PropertyCondition]::new(
            [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
            [System.Windows.Automation.ControlType]::Document
        )
    )
    if ($documents.Count -ne 1) { throw 'QA_WEBVIEW_DOCUMENT_NOT_UNIQUE' }
    $root = $documents.Item(0)
}
$elements = $root.FindAll(
    [System.Windows.Automation.TreeScope]::Descendants,
    [System.Windows.Automation.Condition]::TrueCondition
)
if ($Action -eq 'ListOptions') {
    $items = @(
        for ($i = 0; $i -lt $elements.Count; $i++) {
            $item = $elements.Item($i)
            if ($item.Current.ControlType -eq [System.Windows.Automation.ControlType]::ListItem -and
                $item.Current.Name.Length -le 128) { $item.Current.Name }
        }
    )
    if ($items.Count -gt 64) { throw 'QA_WEBVIEW_OPTION_LIMIT' }
    [pscustomobject]@{ options = $items } | ConvertTo-Json -Compress
    return
}
if ($Action -eq 'Fingerprint') {
    $fingerprints = @(@(
        for ($i = 0; $i -lt $elements.Count; $i++) {
            $text = $elements.Item($i).Current.Name
            if ($text -match 'SHA256:[A-Za-z0-9+/]{43}') { $Matches[0] }
        }
    ) | Select-Object -Unique)
    if ($fingerprints.Count -ne 1) { throw 'QA_WEBVIEW_FINGERPRINT_NOT_UNIQUE' }
    [pscustomobject]@{ fingerprint = $fingerprints[0] } | ConvertTo-Json -Compress
    return
}
if ($Action -eq 'FindText') {
    if (-not $Name -or $Name.Length -gt 160) { throw 'QA_WEBVIEW_TEXT_NAME_INVALID' }
    $found = $false
    for ($i = 0; $i -lt $elements.Count; $i++) {
        if ($elements.Item($i).Current.Name.Contains($Name)) { $found = $true; break }
    }
    [pscustomobject]@{ found = $found; query = $Name } | ConvertTo-Json -Compress
    return
}
if ($Action -eq 'ReadFindings') {
    $inside = $false
    $items = @()
    for ($i = 0; $i -lt $elements.Count; $i++) {
        $element = $elements.Item($i)
        $value = $element.Current.Name.Trim()
        if ($value -eq 'Замечания') { $inside = $true; continue }
        if (-not $inside) { continue }
        if ($value -eq 'Этапы плана' -or $value -eq 'Защищённые выходные файлы') { break }
        if ($element.Current.ControlType -notin @(
            [System.Windows.Automation.ControlType]::Text,
            [System.Windows.Automation.ControlType]::ListItem
        )) { continue }
        if ($value.Length -gt 0 -and $value.Length -le 768 -and $items.Count -lt 24) {
            $items += $value
        }
    }
    [pscustomobject]@{ findingsText = $items } | ConvertTo-Json -Compress
    return
}
if ($Action -eq 'ReadPlanState') {
    # The Plan page exposes only bounded, safe plan diagnostics. Never read
    # Edit/Password controls or arbitrary document values through this action.
    $items = @()
    for ($i = 0; $i -lt $elements.Count; $i++) {
        $element = $elements.Item($i)
        if ($element.Current.ControlType -ne [System.Windows.Automation.ControlType]::Text) { continue }
        $value = $element.Current.Name.Trim()
        if ($value.Length -gt 0 -and $value.Length -le 180 -and $items.Count -lt 48) {
            $items += $value
        }
    }
    [pscustomobject]@{ planText = $items } | ConvertTo-Json -Compress
    return
}
if ($Action -eq 'ReadDeploymentTargets') {
    # Read only the bounded, rendered target labels for one named plan action.
    # This is UI Automation evidence, not a Wails/Core method call.
    if ($Name -notmatch '^qa-[a-z0-9-]{1,80}$') { throw 'QA_WEBVIEW_DEPLOYMENT_NAME_INVALID' }
    $result = @{}
    foreach ($kind in @('Apply', 'Verify')) {
        $summary = "$kind service deployment $Name"
        $matches = @(
            for ($i = 0; $i -lt $elements.Count; $i++) {
                if ($elements.Item($i).Current.ControlType -eq [System.Windows.Automation.ControlType]::Text -and
                    $elements.Item($i).Current.Name.Trim() -eq $summary) { $i }
            }
        )
        if ($matches.Count -ne 1) { throw 'QA_WEBVIEW_DEPLOYMENT_ACTION_NOT_UNIQUE' }
        $following = @(
            for ($i = $matches[0] + 1; $i -lt [Math]::Min($matches[0] + 8, $elements.Count); $i++) {
                if ($elements.Item($i).Current.ControlType -eq [System.Windows.Automation.ControlType]::Text) {
                    $elements.Item($i).Current.Name.Trim()
                }
            }
        )
        if ($following -notcontains $Name) { throw 'QA_WEBVIEW_DEPLOYMENT_LABEL_MISMATCH' }
        $hosts = @($following | Where-Object { $_ -match '^node[0-9]+(, node[0-9]+)*$' })
        if ($hosts.Count -ne 1) { throw 'QA_WEBVIEW_DEPLOYMENT_TARGETS_NOT_UNIQUE' }
        $result[$kind.ToLowerInvariant()] = $hosts[0]
    }
    [pscustomobject]@{ deployment = $Name; applyTargets = $result['apply']; verifyTargets = $result['verify'] } |
        ConvertTo-Json -Compress
    return
}
if ($Action -eq 'ReadPlanTail') {
    # Bounded rendered Text only: no Edit values, DOM, bindings, or raw events.
    $items = @()
    for ($i = 0; $i -lt $elements.Count; $i++) {
        $element = $elements.Item($i)
        if ($element.Current.ControlType -ne [System.Windows.Automation.ControlType]::Text) { continue }
        $value = $element.Current.Name.Trim()
        if ($value.Length -gt 0 -and $value.Length -le 180) { $items += $value }
    }
    if ($items -notcontains 'Установка') { throw 'QA_WEBVIEW_INSTALLATION_PAGE_REQUIRED' }
    [pscustomobject]@{ tailText = @($items | Select-Object -Last 28) } | ConvertTo-Json -Compress
    return
}
if ($Action -eq 'ReadRunEvents') {
    # Read only the bounded, already-rendered safe event list from the real
    # Installation WebView. Never inspect form values, DOM, bindings or raw logs.
    if (-not @($elements | Where-Object { $_.Current.Name -and $_.Current.Name.Trim() -eq 'Ход выполнения' }).Count) {
        throw 'QA_WEBVIEW_RUN_EVENTS_NOT_VISIBLE'
    }
    $items = @(
        for ($i = 0; $i -lt $elements.Count; $i++) {
            $element = $elements.Item($i)
            if ($element.Current.ControlType -ne [System.Windows.Automation.ControlType]::ListItem) { continue }
            $value = if ($element.Current.Name) { $element.Current.Name.Trim() } else { '' }
            if ($value.Length -gt 0 -and $value.Length -le 320) { $value }
        }
    )
    if ($items.Count -gt 64) { $items = @($items | Select-Object -Last 64) }
    [pscustomobject]@{ safeEvents = $items } | ConvertTo-Json -Compress
    return
}
if ($Action -eq 'ReadServerTail') {
    # Read only bounded rendered labels/diagnostics, never form Edit values.
    $items = @()
    for ($i = 0; $i -lt $elements.Count; $i++) {
        $element = $elements.Item($i)
        if ($element.Current.ControlType -ne [System.Windows.Automation.ControlType]::Text) { continue }
        $value = $element.Current.Name.Trim()
        if ($value.Length -gt 0 -and $value.Length -le 180) { $items += $value }
    }
    if ($items -notcontains 'Серверы') { throw 'QA_WEBVIEW_SERVERS_PAGE_REQUIRED' }
    [pscustomobject]@{ tailText = @($items | Select-Object -Last 24) } | ConvertTo-Json -Compress
    return
}
if ($Action -eq 'ReadSensitivePresence') {
    if ($Name -notin @('Абсолютный путь к приватному ключу', 'SSH-пароль', 'Пароль хранилища PKI', 'Default user password', 'Administrator password', 'Monitor healthcheck credential password', 'Monitor credential password', 'Replication credential password')) {
        throw 'QA_WEBVIEW_SENSITIVE_PRESENCE_NAME_INVALID'
    }
    $field = @($elements | Where-Object { $_.Current.ControlType -eq [System.Windows.Automation.ControlType]::Edit -and $_.Current.Name -eq $Name })
    if ($field.Count -ne 1) { throw 'QA_WEBVIEW_SENSITIVE_PRESENCE_NOT_UNIQUE' }
    $pattern = $null
    if (-not $field[0].TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern, [ref]$pattern)) {
        throw 'QA_WEBVIEW_SENSITIVE_PRESENCE_UNAVAILABLE'
    }
    [pscustomobject]@{ control = $Name; present = ($pattern.Current.Value.Length -gt 0) } | ConvertTo-Json -Compress
    return
}
if ($Action -eq 'ReadCapacity') {
    $matches = @(
        for ($i = 0; $i -lt $elements.Count; $i++) {
            if ($elements.Item($i).Current.Name.Trim() -eq 'Черновик:') { $i }
        }
    )
    if ($matches.Count -lt 1) { throw 'QA_WEBVIEW_CAPACITY_LABEL_MISSING' }
    $groups = @(
        foreach ($start in $matches) {
            $parts = @()
            for ($i = $start; $i -lt [Math]::Min($start + 8, $elements.Count); $i++) {
                $value = $elements.Item($i).Current.Name.Trim()
                if ($value -and $value.Length -le 32 -and $value -match '^(Черновик:|из|осталось|·|[0-9]{1,2})$') {
                    $parts += $value
                }
            }
            if ($parts.Count -gt 0) { ,$parts }
        }
    )
    [pscustomobject]@{ capacityTextParts = $groups } | ConvertTo-Json -Compress
    return
}
if ($Action -eq 'ReadStatus') {
    if ($Name -notin @('Проверка:', 'Подготовка:')) { throw 'QA_WEBVIEW_STATUS_NAME_INVALID' }
    $statuses = @(
        for ($i = 0; $i -lt $elements.Count; $i++) {
            $element = $elements.Item($i)
            $value = $element.Current.Name
            if ($value.StartsWith($Name) -and $value.Length -le 240) { $i }
        }
    )
    if ($statuses.Count -ne 1) { throw 'QA_WEBVIEW_STATUS_NOT_UNIQUE' }
    $parts = @()
    for ($i = $statuses[0]; $i -lt [Math]::Min($statuses[0] + 4, $elements.Count); $i++) {
        $value = $elements.Item($i).Current.Name
        if ($value -and $value.Length -le 240) { $parts += $value }
    }
    [pscustomobject]@{ status = ($parts -join ' ') } | ConvertTo-Json -Compress
    return
}
$controls = @(
    for ($i = 0; $i -lt $elements.Count; $i++) {
        $element = $elements.Item($i)
        $type = $element.Current.ControlType
        if ($type -eq [System.Windows.Automation.ControlType]::Button -or
            $type -eq [System.Windows.Automation.ControlType]::TabItem -or
            $type -eq [System.Windows.Automation.ControlType]::Edit -or
            $type -eq [System.Windows.Automation.ControlType]::ComboBox -or
            $type -eq [System.Windows.Automation.ControlType]::Spinner -or
            $type -eq [System.Windows.Automation.ControlType]::CheckBox -or
            $type -eq [System.Windows.Automation.ControlType]::ListItem -or
            ($Action -eq 'ScrollIntoView' -and $type -eq [System.Windows.Automation.ControlType]::DataItem)) {
            $element
        }
    }
)
if ($Action -eq 'Snapshot') {
    $seen = @{}
    @($controls | Where-Object {
        $_.Current.ControlType -ne [System.Windows.Automation.ControlType]::ListItem
    } | ForEach-Object {
        $element = $_
        $type = $element.Current.ControlType.ProgrammaticName
        $label = $element.Current.Name
        $key = "$type`:$label"
        $index = 0
        if ($seen.ContainsKey($key)) { $index = $seen[$key] }
        $seen[$key] = $index + 1
        [pscustomobject]@{
            type = $type
            name = $label
            ordinal = $index
            enabled = $element.Current.IsEnabled
        }
    }) | ConvertTo-Json -Compress
    return
}

if (-not $Name) { throw 'QA_WEBVIEW_CONTROL_NAME_REQUIRED' }
$wantedType = switch ($Action) {
    'Invoke' { [System.Windows.Automation.ControlType]::Button }
    'Select' { [System.Windows.Automation.ControlType]::ListItem }
    'SelectTab' { [System.Windows.Automation.ControlType]::TabItem }
    'AddSelection' { [System.Windows.Automation.ControlType]::ListItem }
    'ScrollIntoView' { [System.Windows.Automation.ControlType]::DataItem }
    'Expand' { [System.Windows.Automation.ControlType]::ComboBox }
    'ChooseOption' { [System.Windows.Automation.ControlType]::ComboBox }
    'ChooseOptionByKeyboard' { [System.Windows.Automation.ControlType]::ComboBox }
    'ReadSelectedOption' { [System.Windows.Automation.ControlType]::ComboBox }
    'ReadToggle' { [System.Windows.Automation.ControlType]::CheckBox }
    'Toggle' { [System.Windows.Automation.ControlType]::CheckBox }
    default { [System.Windows.Automation.ControlType]::Edit }
}
$matches = @($controls | Where-Object {
    ($_.Current.ControlType -eq $wantedType -or
        ($Action -in @('SetText', 'TypeText', 'ReadValue') -and $_.Current.ControlType -eq
            [System.Windows.Automation.ControlType]::Spinner)) -and
    $_.Current.Name -eq $Name
})
if ($Ordinal -ge $matches.Count) { throw 'QA_WEBVIEW_CONTROL_NOT_FOUND' }
$target = $matches[$Ordinal]
if (-not $target.Current.IsEnabled -and $Action -notin @('ReadValue', 'ReadSelectedOption', 'ReadToggle')) {
    throw 'QA_WEBVIEW_CONTROL_DISABLED'
}

if ($Action -eq 'ReadToggle') {
    $pattern = $null
    if (-not $target.TryGetCurrentPattern(
        [System.Windows.Automation.TogglePattern]::Pattern, [ref]$pattern
    )) { throw 'QA_WEBVIEW_TOGGLE_UNAVAILABLE' }
    [pscustomobject]@{ control = $Name; ordinal = $Ordinal; state = $pattern.Current.ToggleState.ToString() } |
        ConvertTo-Json -Compress
    return
}

if ($Action -eq 'ReadSelectedOption') {
    if ($Name -match '(?i)password|secret|token|credential|ключ|парол|секрет') {
        throw 'QA_WEBVIEW_SENSITIVE_VALUE_FORBIDDEN'
    }
    $pattern = $null
    if ($target.TryGetCurrentPattern(
        [System.Windows.Automation.SelectionPattern]::Pattern, [ref]$pattern
    )) {
        $selected = $pattern.Current.GetSelection()
        if ($selected.Count -ne 1) { throw 'QA_WEBVIEW_SELECTION_NOT_UNIQUE' }
        $selectedName = $selected[0].Current.Name
    } elseif ($target.TryGetCurrentPattern(
        [System.Windows.Automation.ValuePattern]::Pattern, [ref]$pattern
    )) {
        $selectedName = $pattern.Current.Value
    } else {
        throw 'QA_WEBVIEW_SELECTION_UNAVAILABLE'
    }
    if ($selectedName.Length -gt 128) { throw 'QA_WEBVIEW_SELECTION_TOO_LONG' }
    [pscustomobject]@{ control = $Name; ordinal = $Ordinal; selected = $selectedName } |
        ConvertTo-Json -Compress
    return
}

if ($Action -eq 'ReadValue') {
    if ($target.Current.IsPassword -or $Name -match '(?i)password|secret|token|credential|ключ|парол|секрет') {
        throw 'QA_WEBVIEW_SENSITIVE_VALUE_FORBIDDEN'
    }
    $pattern = $null
    if (-not $target.TryGetCurrentPattern(
        [System.Windows.Automation.ValuePattern]::Pattern, [ref]$pattern
    )) { throw 'QA_WEBVIEW_VALUE_UNAVAILABLE' }
    $value = $pattern.Current.Value
    if ($value.Length -gt 4096) { throw 'QA_WEBVIEW_VALUE_TOO_LONG' }
    [pscustomobject]@{ control = $Name; ordinal = $Ordinal; value = $value } |
        ConvertTo-Json -Compress
    return
}

if ($Action -eq 'Invoke') {
    $pattern = $null
    if (-not $target.TryGetCurrentPattern(
        [System.Windows.Automation.InvokePattern]::Pattern, [ref]$pattern
    )) { throw 'QA_WEBVIEW_INVOKE_UNAVAILABLE' }
    $pattern.Invoke()
} elseif ($Action -in @('Select', 'SelectTab')) {
    $pattern = $null
    if (-not $target.TryGetCurrentPattern(
        [System.Windows.Automation.SelectionItemPattern]::Pattern, [ref]$pattern
    )) { throw 'QA_WEBVIEW_SELECT_UNAVAILABLE' }
    $pattern.Select()
} elseif ($Action -eq 'AddSelection') {
    $pattern = $null
    if (-not $target.TryGetCurrentPattern(
        [System.Windows.Automation.SelectionItemPattern]::Pattern, [ref]$pattern
    )) { throw 'QA_WEBVIEW_SELECT_UNAVAILABLE' }
    $pattern.AddToSelection()
} elseif ($Action -eq 'Expand') {
    $pattern = $null
    if (-not $target.TryGetCurrentPattern(
        [System.Windows.Automation.ExpandCollapsePattern]::Pattern, [ref]$pattern
    )) { throw 'QA_WEBVIEW_EXPAND_UNAVAILABLE' }
    $pattern.Expand()
} elseif ($Action -eq 'ChooseOption') {
    if (-not $OptionName) { throw 'QA_WEBVIEW_OPTION_NAME_REQUIRED' }
    $pattern = $null
    if (-not $target.TryGetCurrentPattern(
        [System.Windows.Automation.ExpandCollapsePattern]::Pattern, [ref]$pattern
    )) { throw 'QA_WEBVIEW_EXPAND_UNAVAILABLE' }
    $pattern.Expand()
    # Chromium exposes native select choices as document descendants, not
    # necessarily as descendants of the owning ComboBox.
    $choices = @()
    for ($attempt = 0; $attempt -lt 50 -and $choices.Count -ne 1; $attempt++) {
        $freshDocuments = $matchingWindows[0].FindAll(
            [System.Windows.Automation.TreeScope]::Descendants,
            [System.Windows.Automation.PropertyCondition]::new(
                [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
                [System.Windows.Automation.ControlType]::Document
            )
        )
        if ($freshDocuments.Count -ne 1) { throw 'QA_WEBVIEW_DOCUMENT_NOT_UNIQUE' }
        $items = $freshDocuments.Item(0).FindAll(
            [System.Windows.Automation.TreeScope]::Descendants,
            [System.Windows.Automation.PropertyCondition]::new(
                [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
                [System.Windows.Automation.ControlType]::ListItem
            )
        )
        $choices = @(
            for ($i = 0; $i -lt $items.Count; $i++) {
                $item = $items.Item($i)
                if ($item.Current.Name -eq $OptionName) { $item }
            }
        )
        if ($choices.Count -ne 1) { Start-Sleep -Milliseconds 100 }
    }
    if ($choices.Count -ne 1) { throw "QA_WEBVIEW_OPTION_NOT_UNIQUE:$($choices.Count)" }
    $selection = $null
    if (-not $choices[0].TryGetCurrentPattern(
        [System.Windows.Automation.SelectionItemPattern]::Pattern, [ref]$selection
    )) { throw 'QA_WEBVIEW_SELECT_UNAVAILABLE' }
    $selection.Select()
} elseif ($Action -eq 'ChooseOptionByKeyboard') {
    if (-not $OptionName) { throw 'QA_WEBVIEW_OPTION_NAME_REQUIRED' }
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class QaWebViewForeground {
    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr window);
}
'@
    $windowHandle = [IntPtr]$matchingWindows[0].Current.NativeWindowHandle
    if ($windowHandle -eq [IntPtr]::Zero -or
        -not [QaWebViewForeground]::SetForegroundWindow($windowHandle)) {
        throw 'QA_WEBVIEW_FOREGROUND_UNAVAILABLE'
    }
    $target.SetFocus()
    [System.Windows.Forms.SendKeys]::SendWait('{HOME}')
    for ($index = 0; $index -lt $OptionIndex; $index++) {
        [System.Windows.Forms.SendKeys]::SendWait('{DOWN}')
    }
    [System.Windows.Forms.SendKeys]::SendWait('{ENTER}')
} elseif ($Action -eq 'Toggle') {
    $pattern = $null
    if (-not $target.TryGetCurrentPattern(
        [System.Windows.Automation.TogglePattern]::Pattern, [ref]$pattern
    )) { throw 'QA_WEBVIEW_TOGGLE_UNAVAILABLE' }
    $pattern.Toggle()
} elseif ($Action -eq 'Focus') {
    $target.SetFocus()
} elseif ($Action -eq 'ScrollIntoView') {
    if ($Name.Length -gt 64) { throw 'QA_WEBVIEW_SCROLL_ITEM_NAME_INVALID' }
    $pattern = $null
    if (-not $target.TryGetCurrentPattern(
        [System.Windows.Automation.ScrollItemPattern]::Pattern, [ref]$pattern
    )) { throw 'QA_WEBVIEW_SCROLL_ITEM_UNAVAILABLE' }
    $pattern.ScrollIntoView()
} else {
    if ($InputEnvVar) {
        if ($InputEnvVar -cnotmatch '^[A-Z][A-Z0-9_]{0,63}$') {
            throw 'QA_WEBVIEW_INPUT_ENV_NAME_INVALID'
        }
        $value = [Environment]::GetEnvironmentVariable($InputEnvVar)
        if ($null -eq $value) { throw 'QA_WEBVIEW_INPUT_ENV_MISSING' }
    } else {
        if (-not [Console]::IsInputRedirected) { throw 'QA_WEBVIEW_STDIN_REQUIRED' }
        $value = [Console]::In.ReadToEnd()
    }
    if ($value.Length -gt 16384) { throw 'QA_WEBVIEW_INPUT_TOO_LONG' }
    if ($Action -eq 'TypeText') {
        if ($value -notmatch '^[A-Za-z0-9._:/\\ -]*$') { throw 'QA_WEBVIEW_KEYBOARD_TEXT_INVALID' }
        Add-Type -AssemblyName System.Windows.Forms
        $target.SetFocus()
        Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class QaWebViewForegroundCheck {
    [DllImport("user32.dll")]
    public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")]
    public static extern uint GetWindowThreadProcessId(IntPtr window, out uint processId);
}
'@
        $foreground = [QaWebViewForegroundCheck]::GetForegroundWindow()
        [uint32]$foregroundProcessId = 0
        [void][QaWebViewForegroundCheck]::GetWindowThreadProcessId($foreground, [ref]$foregroundProcessId)
        if ($foregroundProcessId -ne $processId) { throw 'QA_WEBVIEW_FOREGROUND_UNAVAILABLE' }
        [System.Windows.Forms.SendKeys]::SendWait('^a')
        [System.Windows.Forms.SendKeys]::SendWait($value)
        [pscustomobject]@{ action = $Action; control = $Name; ordinal = $Ordinal; completed = $true } |
            ConvertTo-Json -Compress
        return
    }
    $pattern = $null
    if (-not $target.TryGetCurrentPattern(
        [System.Windows.Automation.ValuePattern]::Pattern, [ref]$pattern
    )) { throw 'QA_WEBVIEW_VALUE_UNAVAILABLE' }
    $pattern.SetValue($value)
}
[pscustomobject]@{ action = $Action; control = $Name; ordinal = $Ordinal; completed = $true } |
    ConvertTo-Json -Compress
