import streamlit as st
import pandas as pd
import numpy as np
import pm4py
from PIL import Image
import re
import os

# --- PAGE CONFIG ---
st.set_page_config(page_title="Procure-to-Pay (P2P) Process Mining", layout="wide")

# --- INITIALIZATION & DATA LOADING ---
@st.cache_data
def load_data():
    # Attempt to load the dataset
    try:
        dataset = pd.read_csv('sample-dataset/df_event_sample1.csv')
    except FileNotFoundError:
        st.error("File 'df_event_sample1.csv' not found.")
        return None

    # Drop Unnamed columns
    dataset = dataset.loc[:, ~dataset.columns.str.contains('^Unnamed')]
    
    # Cleaning years and types
    year_filter = [2020, 2021, 2022, 2023, 2024, 2025]
    df = dataset.copy()
    
    # Ensure po_number is int
    if 'po_number' in df.columns:
        df['po_number'] = pd.to_numeric(df['po_number'], errors='coerce').fillna(0).astype(int)
    
    # Filter by year and handle timestamps
    df['date_str'] = df['date'].astype(str).str[0:4]
    df = df[df['date_str'].isin([str(y) for y in year_filter])].reset_index(drop=True)
    df['timestamp'] = pd.to_datetime(df['date'], format='ISO8601')
    
    cols_to_keep = ['po_number','pr_po_no','uid_number','activity','date','timestamp',
                    'item','item_line','po_line','gr_number','gr_line','inv_line','wf_line']
    return df[cols_to_keep]

df_raw = load_data()


# PM Display function
def pm_display(ocel_data, df_filtered, object_or_event_filter,
              act_metric, edge_metric, time_op):
    # Filtering OCEL
    if object_or_event_filter == object_filter:
        ocel = pm4py.filter_ocel_object_attribute(ocel_data, "ocel:type", selected_filter, positive=True)
    else:
        ocel = pm4py.filter_ocel_start_events_per_object_type(ocel_data, selected_filter)
        
    ocel = pm4py.filter_ocel_event_attribute(ocel, "ocel:activity", final_activities, positive=True)
    
    # Discover & Visualize
    ocdfg = pm4py.discover_ocdfg(ocel)
    
    # Save and display images
    pm4py.save_vis_ocdfg(ocdfg, 'diag_count.png', annotation='frequency', act_metric=act_metric, edge_metric=edge_metric)
    pm4py.save_vis_ocdfg(ocdfg, 'diag_time.png', annotation='performance', performance_aggregation=time_op, act_metric='events')
    
    st.subheader(" ")
    st.subheader("Log Event Data Display")
    st.dataframe(df_filtered.head(50))
    
    st.subheader("Process Mining - Events Count")
    st.image("diag_count.png")
    st.text("")
    
    st.subheader("Process Mining - Time Lapse")
    st.image("diag_time.png")
    st.text("")
    st.markdown("Remark : Time displayed is the " + f"**{time_op}**" + " of the time taken.")
    st.text("")

    # Downloads
    with open("diag_count.png", "rb") as f:
        st.text("")
        st.download_button("Download Count Diagram", f, "count_diagram.png")
    with open("diag_time.png", "rb") as f:
        st.download_button("Download Time Diagram", f, "time_diagram.png")
        st.markdown("\n\n \n\n")

    st.caption("Note on PM purposes: " +\
        " ● Streamline an Order-to-Cash cycle or audit financial workflows, this app transforms raw event data into actionable insights for continuous process improvement. " +\
        " ● Bottleneck & Variant Analysis: Identify _spaghetti_ processes and hidden delays where cases get stuck, helping you reduce cycle times and operational costs. " +\
        " ● Conformance Checking: Compare real-world execution against your designed business models to flag deviations and ensure regulatory compliance. " +\
        " ● Advanced Data Integration: Built on industry-standard libraries like PM4Py and Pandas, our app handles massive datasets with the flexibility of Python’s analytical ecosystem.\n"
    )


if df_raw is not None:
    st.title("Procure-to-Pay (P2P) Process Mining (PM) :pick:\n")

    st.markdown("_This is a Python-powered P2P PM demo app that extracts knowledge from event logs and instantly " + \
            "visualizes your actual workflows (Directly-Follows Graphs) to see how work really happens, " + \
            "beyond the idealized manual flowcharts._\n")

    # --- SIDEBAR FILTERS (STEP 0) ---
    st.sidebar.header("Define Dataset Filters")
    
    # Date Range Slider
    min_ts = df_raw['timestamp'].min().to_pydatetime()
    max_ts = df_raw['timestamp'].max().to_pydatetime()
    date_range = st.sidebar.slider("Select Date Range", min_ts, max_ts, (min_ts, max_ts))

    # PO Filtering
    all_pos = st.sidebar.checkbox("Include all POs?", value=True)
    po_list = []
    if not all_pos:
        po_input = st.sidebar.text_input("Enter POs (comma separated)")
        po_list = [x.strip() for x in re.split(r',|, ', po_input) if x.strip()]

    # Invoice Filtering
    all_invs = st.sidebar.checkbox("Include all Invoices?", value=True)
    inv_list = []
    if not all_invs:
        inv_input = st.sidebar.text_input("Enter Invoices (comma separated)")
        inv_list = [x.strip() for x in re.split(r',|, ', inv_input) if x.strip()]

    # --- APPLY FILTERS ---
    df_filtered = df_raw[(df_raw.timestamp >= date_range[0]) & (df_raw.timestamp <= date_range[1])]

    if po_list:
        df_filtered = df_filtered[df_filtered['po_number'].astype(str).isin(po_list)]
    
    if inv_list:
        po_of_invoice = df_raw[df_raw.uid_number.astype(str).isin(inv_list)].po_number.unique().tolist()
        df_filtered = df_filtered[df_filtered['po_number'].isin(po_of_invoice)]
        df_filtered = df_filtered[(df_filtered.uid_number.isna()) | (df_filtered.uid_number.astype(str).isin(inv_list))]

    # --- STEP 1: OBJECT / EVENT FILTER ---

    st.header("1) Define Object / Event Filter")

    object_filter = "Object Filter (View PM Diagram based on the entire SKU item / document flow)"
    start_event_filter = "Start Event   (View PM Diagram starting at a specific event)"

    filter_type = st.radio("Set display either by an entire SKU item / document flow or to start at a specific event e.g. starts at Invoicing event rather than Purchase Request event." ,
                           [object_filter, 
                            start_event_filter])
    
    obj_options = ['item', 'po', 'gr', 'inv', 'wf']
    if filter_type == object_filter:
        selected_objects = st.multiselect("Select Objects", 
                                          obj_options, 
                                          default=['item'])
        st.caption("● item: SKU item ● po:Purchase Order ● gr:Goods Receipt " +\
                   "● inv:Invoice ● wf:Workflow/Issue Ticket"
                   )
    else:
        selected_start_event = st.selectbox("Select Start Event Type", 
                                            obj_options,
                                            default = ['item'])

    # --- STEP 2: ACTIVITIES FILTER ---
    st.header("2) Define Activities Filter")
    
    pr_acts = ['PR Cancelled', 'PR Purchase Request']
    po_acts = ['PO From SAP', 'PO From WISE']
    gr_acts = ['GR (PO reversal)', 'GR (Return)', 'GR Goods Receipt']
    inv_acts = ['Invoice Created','Invoice Errors','Invoice Payment','Invoice Posted','Invoice Unprocessed',
                'Invoice WF_DP_APPROV','Invoice WF_FI_APPROV','Invoice WF_GL_DISCREP','Invoice WF_GR_MISSING',
                'Invoice WF_PO_MISSING','Invoice WF_PRICE_DISC','Invoice WF_QUANT_DISC','Invoice WF_Unknown']
    wf_acts = ['WF Data_Update', 'WF FI_APPROV_Being processed', 'WF FI_APPROV_Declined', 'WF FI_APPROV_Recalled',
                'WF FI_APPROV_Released', 'WF FI_APPROV_Sent', 'WF GR_Missing_Being processed', 'WF GR_Missing_Declined',
                'WF GR_Missing_Recalled', 'WF GR_Missing_Released', 'WF GR_Missing_Sent', 'WF INFO_Being processed',
                'WF INFO_Declined', 'WF INFO_Recalled', 'WF INFO_Released', 'WF INFO_Sent', 'WF PO_MISSING_Being processed',
                'WF PO_MISSING_Declined', 'WF PO_MISSING_Recalled', 'WF PO_MISSING_Released', 'WF PO_MISSING_Sent',
                'WF PRICE_DISC_Declined', 'WF PRICE_DISC_Recalled', 'WF PRICE_DISC_Released', 'WF PRICE_DISC_Sent']
    
    all_available_acts = pr_acts + po_acts + gr_acts + inv_acts + wf_acts
    
    act_mode = st.radio("Select activities to be included in the PM diagram.\n"
                        " Fewer activities inclusion increases diagram comprehension.", 
                        ["All", "Main activities", "Sub-activities"],
                         index = 1 # Default selection
                         )
    
    selected_acts = []
    if act_mode == "All":
        selected_acts = all_available_acts
    elif act_mode == "Main activities":
        groups = st.multiselect("Select main activities", 
                                ["PR", "PO", "GR", "Invoicing", "Workflow"],
                                default = ["PO", "GR"])
        group_map = {"PR": pr_acts, "PO": po_acts, "GR": gr_acts, "Invoicing": inv_acts, "Workflow": wf_acts}
        for g in groups:
            selected_acts.extend(group_map[g])
    else:
        selected_acts = st.multiselect("Select Individual Activities", 
                                       all_available_acts, 
                                       default = po_acts[:1]
                                       )

    exclude_acts = st.multiselect("Exclude Activities. Select activities you wish to exclude.", selected_acts)
    final_activities = [a for a in selected_acts if a not in exclude_acts]

    # --- STEP 3: DIAGRAM SETTING ---
    st.header("3) Diagram Setting")
    st.markdown("**Activity metric selection**: Trace the count of objects (SKU items / documents) or the number of event occurrences. " +
                "This is displayed in the boxes as _**UO=n**_ or _**E=n**_ .") 
    st.markdown("**Edge metric selection**: Display either the number of events couplings or the number of SKU items / documents flowing between processes. " + 
                "This is displayed on top of arrows as _**UO=n**_ or _**EC=n**_ .")
    st.markdown("**Time metric selection**: Display either the **mean** or the **sum** of time taken between processes in the **Time Lapse diagram**. ")
    col1, col2, col3 = st.columns(3)
    with col1:
        act_metric = st.radio("Activity Metric", 
                              ['unique_objects', 'events'],
                              index=0)
    with col2:
        edge_metric = st.radio("Edge Metric", 
                               ['unique_objects', 'event_couples'], 
                               index=0)
    with col3:
        time_op = st.radio("Time Metric", 
                           ['mean', 'sum'],
                           index=0)
        
    # OCEL Structuring Logic
    df_ocel_prep = df_filtered.copy()
    df_ocel_prep = df_ocel_prep.drop_duplicates().reset_index(drop=True)
    
    # Internal PM4PY Logic
    df_ocel_prep['ocel:eid'] = 'e' + df_ocel_prep.index.astype(str)
    df_ocel_prep = df_ocel_prep.rename(columns={
        'date': 'ocel:timestamp',
        'activity': 'ocel:activity',
        'item_line': 'ocel:type:item',
        'po_line': 'ocel:type:po',
        'gr_line': 'ocel:type:gr',
        'inv_line': 'ocel:type:inv',
        'wf_line': 'ocel:type:wf'
    })
    
    # Save temp file for PM4PY to read
    df_ocel_prep.to_csv("temp_ocel.csv", index=False)
    ocel_data = pm4py.read_ocel("temp_ocel.csv")

    object_or_event_filter = filter_type

    if object_or_event_filter == object_filter:
        selected_filter = selected_objects
    elif object_or_event_filter == start_event_filter:
        selected_filter = selected_start_event

        
    # Display PM Diagram
    pm_display(ocel_data, df_filtered, object_or_event_filter,
              act_metric, edge_metric, time_op)




    # # --- EXECUTION BUTTON ---
    # if st.button("Generate Dashboard", type="primary"):
    #     # OCEL Structuring Logic
    #     df_ocel_prep = df_filtered.copy()
    #     df_ocel_prep = df_ocel_prep.drop_duplicates().reset_index(drop=True)
        
    #     # Internal PM4PY Logic
    #     df_ocel_prep['ocel:eid'] = 'e' + df_ocel_prep.index.astype(str)
    #     df_ocel_prep = df_ocel_prep.rename(columns={
    #         'date': 'ocel:timestamp',
    #         'activity': 'ocel:activity',
    #         'item_line': 'ocel:type:item',
    #         'po_line': 'ocel:type:po',
    #         'gr_line': 'ocel:type:gr',
    #         'inv_line': 'ocel:type:inv',
    #         'wf_line': 'ocel:type:wf'
    #     })
        
    #     # Save temp file for PM4PY to read
    #     df_ocel_prep.to_csv("temp_ocel.csv", index=False)
    #     ocel = pm4py.read_ocel("temp_ocel.csv")
        
    #     # Filtering OCEL
    #     if filter_type == 'Object Filter':
    #         ocel = pm4py.filter_ocel_object_attribute(ocel, "ocel:type", selected_objects, positive=True)
    #     else:
    #         ocel = pm4py.filter_ocel_start_events_per_object_type(ocel, selected_start_event)
            
    #     ocel = pm4py.filter_ocel_event_attribute(ocel, "ocel:activity", final_activities, positive=True)
        
    #     # Discover & Visualize
    #     ocdfg = pm4py.discover_ocdfg(ocel)
        
    #     # Save and display images
    #     pm4py.save_vis_ocdfg(ocdfg, 'diag_count.png', annotation='frequency', act_metric=act_metric, edge_metric=edge_metric)
    #     pm4py.save_vis_ocdfg(ocdfg, 'diag_time.png', annotation='performance', performance_aggregation=time_op, act_metric='events')
        
    #     st.subheader("Log Event Data")
    #     st.dataframe(df_filtered.head(50))
        
    #     st.subheader("Process Mining - Events Count")
    #     st.image("diag_count.png")
        
    #     st.subheader("Process Mining - Time Lapse")
    #     st.image("diag_time.png")
    #     st.markdown("Remark : Time displayed is the " + f"**{time_op}**" + " of the time taken.")

    #     # Downloads
    #     with open("diag_count.png", "rb") as f:
    #         st.download_button("Download Count Diagram", f, "count_diagram.png")
    #     with open("diag_time.png", "rb") as f:
    #         st.download_button("Download Time Diagram", f, "time_diagram.png")


