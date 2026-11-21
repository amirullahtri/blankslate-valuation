Attribute VB_Name = "BlankSlateMacros"
'==========================================================================================
' BlankSlate Valuation Calculator - VBA macros
' Import this module (Alt+F11 > File > Import File...) and save the workbook as .xlsm.
' The macros only move data and drive recalculation; every valuation formula lives in the
' worksheets, so the logic stays visible and auditable.
'==========================================================================================
Option Explicit

Private Const INPUT_COLOR As Long = 14087423     ' RGB(255,244,214) light yellow
Private Const MISSING_COLOR As Long = 13421823   ' RGB(255,204,204) light red

'------------------------------------------------------------------------------------------
' 1. ImportTemplate: load a filled standard input template for any company
'------------------------------------------------------------------------------------------
Public Sub ImportTemplate()
    Dim f As Variant, src As Workbook
    ' Excel for Mac does not accept the Windows filter string, so it is only passed on Windows.
#If Mac Then
    f = Application.GetOpenFilename()
#Else
    f = Application.GetOpenFilename("Excel files (*.xlsx;*.xlsm),*.xlsx;*.xlsm", , "Select a filled BlankSlate input template")
#End If
    If VarType(f) = vbBoolean Then Exit Sub
    Application.ScreenUpdating = False
    On Error GoTo Fail
    Set src = Workbooks.Open(CStr(f), ReadOnly:=True)
    CopyBlock src, "Company", "C2:D" & LastKeyRow(src, "Company", 2)
    ' The input template carries no defined names, so last_updated is located by position on the
    ' source side: two rows below the last Company key. The target side uses its own name.
    ThisWorkbook.Sheets("Company").Range("c_last_updated").Value = _
        src.Sheets("Company").Cells(LastKeyRow(src, "Company", 2) + 2, 3).Value
    CopyBlock src, "Financials", "D2:J" & LastKeyRow(src, "Financials", 3)
    CopyBlock src, "Market", "C2:D" & LastKeyRow(src, "Market", 2)
    CopyBlock src, "Peers", "A2:M16"
    CopyBlock src, "Assumptions", "C2:C" & LastKeyRow(src, "Assumptions", 2)
    If SheetExists(src, "Risks") Then CopyBlock src, "Risks", "A2:E13"
    CopyBlock src, "Settings", "C2:C6"
    CopyBlock src, "Settings", "C7:E7"
    src.Close SaveChanges:=False
    Application.ScreenUpdating = True
    RefreshAll
    MsgBox "Template imported and model refreshed for " & ThisWorkbook.Sheets("Company").Range("C2").Value & ".", vbInformation
    Exit Sub
Fail:
    Application.ScreenUpdating = True
    If Not src Is Nothing Then src.Close SaveChanges:=False
    MsgBox "Import failed: " & Err.Description & vbCrLf & "Use the standard BlankSlate input template layout.", vbExclamation
End Sub

Private Function WbRange(ByVal addr As String) As Range
    ' Resolve a defined name, or a Sheet!A1 address, against THIS workbook.
    ' A bare Range("name") is Application.Range, which looks the name up on whatever sheet happens
    ' to be active and fails when the name lives on another one ("Method 'Range' of object
    ' '_Global' failed"). Every lookup goes through here so no macro depends on the active sheet.
    If InStr(addr, "!") > 0 Then
        Set WbRange = ThisWorkbook.Sheets(Split(addr, "!")(0)).Range(Split(addr, "!")(1))
    Else
        Set WbRange = ThisWorkbook.Names(addr).RefersToRange
    End If
End Function

Private Function LastKeyRow(wbk As Workbook, sheetName As String, firstRow As Long) As Long
    ' Last row of the input block, found from the key labels in column A rather than hardcoded,
    ' so adding a field to Company or Financials cannot silently drop data on import.
    Dim ws As Worksheet, r As Long
    Set ws = wbk.Sheets(sheetName)
    r = firstRow
    Do While Len(Trim$(CStr(ws.Cells(r, 1).Value))) > 0
        r = r + 1
    Loop
    LastKeyRow = r - 1
End Function

Private Function SheetExists(wbk As Workbook, nm As String) As Boolean
    Dim ws As Worksheet
    On Error Resume Next
    Set ws = wbk.Sheets(nm)
    On Error GoTo 0
    SheetExists = Not ws Is Nothing
End Function

Private Sub CopyBlock(src As Workbook, sheetName As String, addr As String)
    ThisWorkbook.Sheets(sheetName).Range(addr).Value = src.Sheets(sheetName).Range(addr).Value
End Sub

'------------------------------------------------------------------------------------------
' 2. NewCompany: clear all inputs - the empty calculator
'------------------------------------------------------------------------------------------
Public Sub NewCompany()
    If MsgBox("Clear all company inputs and start a new valuation?", vbQuestion + vbYesNo) <> vbYes Then Exit Sub
    With ThisWorkbook
        .Sheets("Company").Range("C2:D" & LastKeyRow(ThisWorkbook, "Company", 2)).ClearContents
        .Sheets("Company").Range("C5").Value = False
        .Sheets("Company").Range("C6").Value = "IDR"
        .Sheets("Company").Range("C7").Value = 1000000000#
        .Sheets("Company").Range("C9").Value = 1000000#
        .Sheets("Company").Range("c_last_updated").Value = Format(Date, "yyyy-mm-dd")
        .Sheets("Financials").Range("D2:J" & LastKeyRow(ThisWorkbook, "Financials", 3)).ClearContents
        .Sheets("Market").Range("C2:D" & LastKeyRow(ThisWorkbook, "Market", 2)).ClearContents
        .Sheets("Market").Range("C6").Value = "user"
        .Sheets("Market").Range("C9").Value = 0.22
        .Sheets("Peers").Range("A2:M16").ClearContents
        .Sheets("Assumptions").Range("C2:C" & LastKeyRow(ThisWorkbook, "Assumptions", 2)).ClearContents
        .Sheets("Risks").Range("A2:E13").ClearContents
        .Sheets("Settings").Range("C2:C6").Value = Application.Transpose(Array(0.15, -0.15, 0.03, 0.02, 0.005))
        .Sheets("Settings").Range("C7:E7").Value = Array(0.25, 0.5, 0.25)
        .Sheets("Sensitivity").Range("B9:G14,B17:G22").ClearContents
        .Sheets("Dashboard").Range("o_scn").Value = "BASE"
        .Sheets("Intrinsic").Range("rev_mult").Value = 1
    End With
    Application.CalculateFull
    ThisWorkbook.Sheets("Company").Activate
    ThisWorkbook.Sheets("Company").Range("C2").Select
End Sub

'------------------------------------------------------------------------------------------
' 3. RefreshAll: recalculate, solve implied growth, run sensitivity grids, stamp the time
'------------------------------------------------------------------------------------------
Public Sub RefreshAll()
    Application.ScreenUpdating = False
    Application.CalculateFull
    SolveImpliedGrowth True
    RunSensitivity
    BuildRiskRegister
    ThisWorkbook.Sheets("Sensitivity").Range("sens_stamp").Value = Format(Now, "yyyy-mm-dd hh:nn")
    Application.CalculateFull
    Application.ScreenUpdating = True
End Sub

Public Sub SolveImpliedGrowth(Optional silent As Boolean = False)
    ' Reverse valuation: growth multiplier at which intrinsic value equals the market price.
    Dim price As Double, ok As Boolean
    price = Val(ThisWorkbook.Sheets("Company").Range("c_price").Value)
    WbRange("rev_mult").Value = 1
    Application.Calculate
    If price <= 0 Or Not IsNumeric(WbRange("v_reverse").Value) Then Exit Sub
    On Error Resume Next
    ok = WbRange("v_reverse").GoalSeek(Goal:=price, ChangingCell:=WbRange("rev_mult"))
    On Error GoTo 0
    If Not ok And Not silent Then MsgBox "No growth path reproduces the market price.", vbInformation
End Sub

Public Sub BuildRiskRegister()
    ' Fills the break-even cells on "Key risks": the level of one driver at which the blended
    ' fair value equals the market price. Excel Goal Seek drives the override cell, then the
    ' original override is restored, so user input is never changed.
    Dim price As Double
    price = Val(WbRange("c_price").Value)
    WbRange("be_margin").Value = "": WbRange("be_growth").Value = ""
    If price <= 0 Or WbRange("chk_err").Value > 0 Then Exit Sub
    If WbRange("r_fin").Value Then
        WbRange("be_margin").Value = BreakEven(WbRange("Assumptions!C9"), price, "ROE ", "0.0%")
    Else
        WbRange("be_margin").Value = BreakEven(WbRange("Assumptions!C4"), price, "EBIT margin ", "0.0%")
    End If
    WbRange("be_growth").Value = BreakEven(WbRange("Assumptions!C3"), price, "g ", "0.00%")
End Sub

Private Function BreakEven(driver As Range, price As Double, label As String, fmt As String) As String
    Dim keep As Variant, ok As Boolean, v As Double
    keep = driver.Value
    On Error Resume Next
    ok = WbRange("o_c_raw").GoalSeek(Goal:=price, ChangingCell:=driver)
    v = Val(driver.Value)
    On Error GoTo 0
    driver.Value = keep
    Application.Calculate
    If ok And IsNumeric(v) Then
        BreakEven = label & Format(v, fmt)
    Else
        BreakEven = "no level in a plausible range reverses the call"
    End If
End Function

Public Sub RunSensitivity()
    Dim ws As Worksheet, i As Integer, j As Integer
    Dim dws, dgs, dg1s, dms
    Set ws = ThisWorkbook.Sheets("Sensitivity")
    dws = Array(-0.02, -0.01, 0, 0.01, 0.02)
    dgs = Array(-0.01, -0.005, 0, 0.005, 0.01)
    dg1s = Array(-0.1, -0.05, 0, 0.05, 0.1)
    dms = Array(-0.04, -0.02, 0, 0.02, 0.04)
    ws.Range("B9:G14,B17:G22").ClearContents
    ' Grid 1: discount rate x terminal growth
    ws.Range("B9").Value = "rate \ g"
    For j = 0 To 4: ws.Cells(9, 3 + j).Value = WbRange("a_g_terminal").Value + dgs(j): Next j
    For i = 0 To 4
        ws.Cells(10 + i, 2).Value = IIf(WbRange("r_fin").Value, WbRange("r_ke").Value, WbRange("r_wacc").Value) + dws(i)
        For j = 0 To 4
            WbRange("sens_dw").Value = dws(i): WbRange("sens_dg").Value = dgs(j)
            WbRange("sens_dg1").Value = 0: WbRange("sens_dm").Value = 0
            Application.Calculate
            ws.Cells(10 + i, 3 + j).Value = WbRange("v_sens").Value
        Next j
    Next i
    ' Grid 2: target margin x year-1 growth (non-financial firms)
    If Not WbRange("r_fin").Value Then
        ws.Range("B17").Value = "margin \ g1"
        For j = 0 To 4: ws.Cells(17, 3 + j).Value = WbRange("a_g1").Value + dg1s(j): Next j
        For i = 0 To 4
            ws.Cells(18 + i, 2).Value = WbRange("a_target_margin").Value + dms(i)
            For j = 0 To 4
                WbRange("sens_dw").Value = 0: WbRange("sens_dg").Value = 0
                WbRange("sens_dg1").Value = dg1s(j): WbRange("sens_dm").Value = dms(i)
                Application.Calculate
                ws.Cells(18 + i, 3 + j).Value = WbRange("v_sens").Value
            Next j
        Next i
    End If
    WbRange("sens_dw").Value = 0: WbRange("sens_dg").Value = 0: WbRange("sens_dg1").Value = 0: WbRange("sens_dm").Value = 0
    ws.Range("B10:B14,C9:G9,B18:B22,C17:G17").NumberFormat = "0.0%"
    ws.Range("C10:G14,C18:G22").NumberFormat = "#,##0"
End Sub

'------------------------------------------------------------------------------------------
' 4. Scenario switch (Dashboard shows the selected scenario's intrinsic value)
'------------------------------------------------------------------------------------------
Public Sub ScenarioBear(): SetScenario "BEAR": End Sub
Public Sub ScenarioBase(): SetScenario "BASE": End Sub
Public Sub ScenarioBull(): SetScenario "BULL": End Sub

Private Sub SetScenario(s As String)
    WbRange("o_scn").Value = s
    Application.Calculate
End Sub

'------------------------------------------------------------------------------------------
' 5. ValidateInputs: highlight missing required inputs, summarise triggered checks
'------------------------------------------------------------------------------------------
Public Sub ValidateInputs()
    Dim req, a, msg As String, nMiss As Long, r As Long, c As Range
    With ThisWorkbook
        .Sheets("Company").Range("C2:C11").Interior.Color = INPUT_COLOR
        .Sheets("Market").Range("C2:C10").Interior.Color = INPUT_COLOR
        .Sheets("Financials").Range("D2:I19").Interior.Color = INPUT_COLOR
    End With
    req = Array("Company!C2", "Company!C4", "Company!C6", "Company!C7", "Company!C8", "Company!C9", "Company!C10", "Company!C11", _
                "Market!C2", "Market!C3")
    For Each a In req
        Set c = WbRange(a)
        If Len(Trim(c.Value & "")) = 0 Then c.Interior.Color = MISSING_COLOR: nMiss = nMiss + 1
    Next a
    ' financial lines that must have a latest value: revenue, EBIT (non-financial), net income, equity, cash, debt
    For Each a In Array(3, 4, 9, 15, 11, 12)
        r = a
        If Application.WorksheetFunction.Count(ThisWorkbook.Sheets("Financials").Range("D" & r & ":I" & r)) = 0 Then
            If Not (r = 4 And WbRange("r_fin").Value) Then
                ThisWorkbook.Sheets("Financials").Range("D" & r & ":I" & r).Interior.Color = MISSING_COLOR
                nMiss = nMiss + 1
            End If
        End If
    Next a
    Application.CalculateFull
    msg = "Missing required inputs: " & nMiss & vbCrLf & _
          "Errors triggered: " & WbRange("chk_err").Value & vbCrLf & _
          "Warnings triggered: " & WbRange("chk_warn").Value & vbCrLf & vbCrLf
    For r = 2 To 18
        With ThisWorkbook.Sheets("Checks")
            If .Cells(r, 3).Value = True And .Cells(r, 1).Value <> "INFO" Then msg = msg & .Cells(r, 1).Value & "  " & .Cells(r, 2).Value & ": " & .Cells(r, 4).Value & vbCrLf
        End With
    Next r
    MsgBox msg, IIf(WbRange("chk_err").Value > 0, vbExclamation, vbInformation), "Input validation"
End Sub

'------------------------------------------------------------------------------------------
' 6. ExportSummary: PDF of the Dashboard + values-only workbook + one row in Log
'------------------------------------------------------------------------------------------
Public Sub ExportSummary()
    Dim stamp As String, base As String, nb As Workbook, ws As Worksheet, lg As Worksheet, r As Long
    Dim tk As String
    RefreshAll
    tk = Trim(ThisWorkbook.Sheets("Company").Range("C3").Value & "")
    If tk = "" Then tk = "company"
    stamp = Format(Now, "yyyymmdd_hhnn")
    base = ThisWorkbook.Path & Application.PathSeparator & tk & "_valuation_" & stamp
    ' The PDF is a convenience, not the deliverable. Excel for Mac refuses this call in some
    ' builds, so a failure here must not abort the workbook export that follows it.
    Dim pdfOK As Boolean
    On Error Resume Next
    ThisWorkbook.Sheets("Dashboard").ExportAsFixedFormat Type:=xlTypePDF, Filename:=base & ".pdf", _
        Quality:=xlQualityStandard, IncludeDocProperties:=True, OpenAfterPublish:=False
    pdfOK = (Err.Number = 0)
    Err.Clear
    On Error GoTo 0
    ThisWorkbook.Sheets(Array("Dashboard", "Decision", "Key risks", "Checks", "Sensitivity")).Copy
    Set nb = ActiveWorkbook
    For Each ws In nb.Worksheets
        ws.UsedRange.Value = ws.UsedRange.Value
    Next ws
    Application.DisplayAlerts = False
    nb.SaveAs Filename:=base & ".xlsx", FileFormat:=51
    nb.Close SaveChanges:=False
    Application.DisplayAlerts = True
    Set lg = ThisWorkbook.Sheets("Log")
    r = lg.Cells(lg.Rows.Count, 1).End(xlUp).Row + 1
    lg.Cells(r, 1).Resize(1, 15).Value = Array(Format(Now, "yyyy-mm-dd hh:nn"), WbRange("c_name").Value, WbRange("c_valuation_date").Value, _
        WbRange("o_price").Value, WbRange("o_intr").Value, WbRange("o_rel").Value, WbRange("o_wi").Value, WbRange("o_c_raw").Value, _
        WbRange("o_low").Value, WbRange("o_high").Value, WbRange("o_up").Value, WbRange("o_call").Value, WbRange("o_conf").Value, _
        WbRange("chk_err").Value, WbRange("chk_warn").Value)
    If pdfOK Then
        MsgBox "Exported:" & vbCrLf & base & ".pdf" & vbCrLf & base & ".xlsx", vbInformation
    Else
        MsgBox "Exported:" & vbCrLf & base & ".xlsx" & vbCrLf & vbCrLf & _
               "The PDF of the Dashboard could not be written on this build of Excel; the workbook holds every figure.", vbInformation
    End If
End Sub

'------------------------------------------------------------------------------------------
' 7. SetupButtons: run once to place macro buttons on the Dashboard
'------------------------------------------------------------------------------------------
Public Sub SetupButtons()
    Dim ws As Worksheet, b, defs, i As Integer, x As Double
    Set ws = ThisWorkbook.Sheets("Dashboard")
    For Each b In ws.Buttons: b.Delete: Next b
    defs = Array(Array("Import template", "ImportTemplate"), Array("New company", "NewCompany"), _
                 Array("Refresh all", "RefreshAll"), Array("Validate inputs", "ValidateInputs"), _
                 Array("Bear", "ScenarioBear"), Array("Base", "ScenarioBase"), Array("Bull", "ScenarioBull"), _
                 Array("Key risks", "BuildRiskRegister"), Array("Export summary", "ExportSummary"))
    x = ws.Range("E2").Left
    For i = 0 To UBound(defs)
        With ws.Buttons.Add(x, ws.Range("E2").Top, IIf(i >= 4 And i <= 6, 48, 92), 22)
            .Caption = defs(i)(0)
            .OnAction = defs(i)(1)
        End With
        x = x + IIf(i >= 4 And i <= 6, 52, 96)
    Next i
End Sub
