import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title='订单价格查询', page_icon=":eyeglasses:")
st.title('订单成本总价')

if st.session_state['cursor'] == '':
    st.warning('你必须先登录')
    st.stop()

if 'df' not in st.session_state:
    st.session_state['df'] = ''

if 'vylist' not in st.session_state:
    st.session_state['vylist'] = []

if 'names' not in st.session_state:
    st.session_state['names'] = []

if 'number_list' not in st.session_state:
    st.session_state['number_list'] = []

def getdf(Tquery):
    st.session_state['cursor'].execute(Tquery)
    rows = st.session_state['cursor'].fetchall()

    # Get column names from the cursor description
    columns = [column[0] for column in st.session_state['cursor'].description]

    # Create DataFrame for the query result
    df_ggdx = pd.DataFrame.from_records(rows, columns=columns)

    # Calculate 米用量(g) (weight) based on 经纬 field
    df_ggdx['米用量(g)'] = df_ggdx.apply(lambda row: row['经重'] if row['经纬'] == '经' else row['纬重'], axis=1)

    # Create DataFrame for quantities and sequence numbers
    numdic = {'数量': st.session_state['number_list'], '序号': st.session_state['vylist']}
    numdf = pd.DataFrame(numdic)

    # Merge dataframes on sequence number
    totaldf = pd.merge(df_ggdx, numdf, on='序号')

    # Calculate total weight
    totaldf['总重(kg)'] = totaldf['米用量(g)'] * totaldf['数量'] / 1000
    totaldf['总重(kg)'] = totaldf['总重(kg)'].astype('float64')
    totaldf.drop(columns=['经重', '纬重', '序号'], inplace=True)

    # Fill in missing '规格' values
    totaldf['规格'] = totaldf['规格'].fillna('未知')

    # Group by 规格 and calculate sums
    totaldf = totaldf.groupby(['经纬','规格']).agg({
        '米用量(g)': 'first', 
        '数量': 'sum',
        '总重(kg)': 'sum'
    }).reset_index()

    return totaldf

# Display form for text input
with st.form("text_input_form"):
    query = '''
    SELECT c_cpbh
    FROM ggd
    '''

    # Execute the query and fetch all rows
    st.session_state['cursor'].execute(query)
    rows = st.session_state['cursor'].fetchall()
    
    # Convert the rows into a list of non-empty, stripped values
    result_list = [row[0].strip() for row in rows if row[0].strip()]

    # Create multiselect for product names
    st.session_state['names'] = st.multiselect('输入品名', result_list)
    
    # Input field for quantities
    nums = st.text_input('输入数量，用空格隔开')
    
    if nums:
        try:
            # Convert input to list of integers
            st.session_state['number_list'] = [int(num.strip()) for num in nums.split()]
        except ValueError:
            st.warning("请用空格隔开输入的数量")

    # Submit button
    submit_button = st.form_submit_button("Submit")

if len(st.session_state['number_list']) == 0 or len(st.session_state['names']) == 0:
    st.stop()

# Logic to process after form submission
if submit_button:
    if len(st.session_state['number_list']) != len(st.session_state['names']):
        st.warning(f"数量不对，输入的数量有：{len(st.session_state['number_list'])}，但是品名有：{len(st.session_state['names'])}")
        st.stop()

    st.session_state['vylist'] = []
    
    # Retrieve n_vy for each name individually to maintain the order
    for name in st.session_state['names']:
        query = f'''
            SELECT n_vy
            FROM ggd
            WHERE c_cpbh = '{name}'
        '''
        st.session_state['cursor'].execute(query)
        vy = st.session_state['cursor'].fetchone()
        if vy:
            st.session_state['vylist'].append(vy[0])  # Append the matching n_vy to vylist
        else:
            st.session_state['vylist'].append(None)  # Append None if no n_vy found (handle it accordingly)

    # Ensure that no None values are present in vylist
    if any(vy is None for vy in st.session_state['vylist']):
        st.warning('某些品名未找到序号，请检查输入')
        st.stop()

    vyqueryHelper = " OR ".join([f"g.n_vy = {r}" for r in st.session_state['vylist']])

    # Main query to fetch product details
    Tquery = f'''
        SELECT g.c_lb AS 经纬, n_dl AS 经重, n_dl1 AS 纬重, y.c_guige AS 规格, g.n_vy AS 序号
        FROM g_ggsx g
        LEFT JOIN yclk y
        ON g.c_zhno = y.c_clbh
        WHERE {vyqueryHelper}
    '''

    st.session_state['df'] = getdf(Tquery)

# Display the grouped result
st.dataframe(st.session_state['df'])


with st.form("input_form"):
    prices = []
    
    # Iterate over DataFrame rows
    for index, row in st.session_state['df'].iterrows():
        price = st.number_input(f"请根据规格输入价格：{row['规格']} 每千克", key=index)
        prices.append(price)
    
    # Submit button for the form
    submit_button_price = st.form_submit_button("Submit")

if submit_button_price:
    # Add the user inputs to a new column in the DataFrame
    st.session_state['df']['价格'] = prices
    st.session_state['df']['成本'] = st.session_state['df']['价格'] * st.session_state['df']['总重(kg)']

    # Display the updated DataFrame
    st.write("总价计算")
    st.dataframe(st.session_state['df'])
    st.header(f"合计原料成本为 {round(sum(st.session_state['df']['成本']),2)}")

    # Function to convert DataFrame to Excel
    def to_excel(df):
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Sheet1')
        processed_data = output.getvalue()
        return processed_data

    excel_data = to_excel(st.session_state['df'])

    st.download_button(
        label="导出为Excel",
        data=excel_data,
        file_name='原材料成本.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

# Display details for each item
for i in range(len(st.session_state['vylist'])):
    vy = st.session_state['vylist'][i]
    curnum = st.session_state['number_list'][i]
    curname = st.session_state['names'][i]

    # Query for details based on sequence number
    query = f'''
    SELECT g.c_lb AS 经纬, n_dl AS 经重, n_dl1 AS 纬重, y.c_guige AS 规格
    FROM g_ggsx g
    LEFT JOIN yclk y
    ON g.c_zhno = y.c_clbh
    WHERE n_vy = {vy}
    '''

    st.session_state['cursor'].execute(query)
    rows = st.session_state['cursor'].fetchall()

    # Get column names from the cursor description
    columns = [column[0] for column in st.session_state['cursor'].description]

    st.divider()
    st.text(f'品名：{curname}，数量：{curnum}')

    # Create DataFrame for individual product details
    df_ggdx = pd.DataFrame.from_records(rows, columns=columns)
    df_ggdx['米用量(g)'] = df_ggdx.apply(lambda row: row['经重'] if row['经纬'] == '经' else row['纬重'], axis=1)
    df_ggdx['总重(kg)'] = df_ggdx['米用量(g)'] * curnum / 1000
    
    # Display specific details
    df = df_ggdx[['经纬', '规格', '米用量(g)', '总重(kg)']]
    st.dataframe(df)

