Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$form = New-Object System.Windows.Forms.Form
$form.Text = 'Win Automator E2E Target'
$form.Size = New-Object System.Drawing.Size(560,360)
$form.StartPosition = 'CenterScreen'

$labels = @('Full Name','Birth Date','Department','Position')
$y = 30
$controls = @{}
foreach ($labelText in $labels) {
    $label = New-Object System.Windows.Forms.Label
    $label.Text = $labelText
    $label.Location = New-Object System.Drawing.Point(25,$y)
    $label.Size = New-Object System.Drawing.Size(120,25)
    $form.Controls.Add($label)

    if ($labelText -eq 'Department') {
        $control = New-Object System.Windows.Forms.ComboBox
        [void]$control.Items.AddRange(@('OP','OMN','AERO'))
        $control.DropDownStyle = 'DropDownList'
    } else {
        $control = New-Object System.Windows.Forms.TextBox
    }
    $control.Name = switch ($labelText) {
        'Full Name' {'txtFullName'}
        'Birth Date' {'txtBirthDate'}
        'Department' {'cmbDepartment'}
        'Position' {'txtPosition'}
    }
    $control.AccessibleName = $labelText
    $control.Location = New-Object System.Drawing.Point(160,$y)
    $control.Size = New-Object System.Drawing.Size(340,25)
    $form.Controls.Add($control)
    $controls[$labelText] = $control
    $y += 55
}

$save = New-Object System.Windows.Forms.Button
$save.Name = 'btnSave'
$save.AccessibleName = 'Save'
$save.Text = 'Save'
$save.Location = New-Object System.Drawing.Point(390,260)
$save.Size = New-Object System.Drawing.Size(110,35)
$save.Add_Click({
    if ([string]::IsNullOrWhiteSpace($env:WIN_AUTOMATOR_E2E_RESULT)) {
        throw 'WIN_AUTOMATOR_E2E_RESULT is required for automated test target.'
    }
    $payload = [PSCustomObject]@{
        full_name = $controls['Full Name'].Text
        birth_date = $controls['Birth Date'].Text
        department = $controls['Department'].Text
        position = $controls['Position'].Text
    } | ConvertTo-Json
    Set-Content -LiteralPath $env:WIN_AUTOMATOR_E2E_RESULT -Value $payload -Encoding UTF8
    $form.Close()
})
$form.Controls.Add($save)

[void]$form.ShowDialog()
