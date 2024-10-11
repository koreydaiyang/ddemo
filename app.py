import streamlit as st
import pyodbc
import pandas as pd
from io import BytesIO

st.set_page_config(
    page_title='达利订单成本查询系统',
)


st.title('达利订单成本查询系统')

if 'cursor' not in st.session_state:
    st.session_state['cursor'] = ''

if 'name' not in st.session_state:
    st.session_state['name'] = ''

if 'maindf' not in st.session_state:
    st.session_state['maindf'] = pd.DataFrame()

if 'vy' not in st.session_state:
    st.session_state['vy'] = ''

if 'infos' not in st.session_state:
    st.session_state['infos'] = []

if 'gf' not in st.session_state:
    st.session_state['gf'] = ''

# Create a form to capture database connection details
with st.form("db_connection_form"):
    username = st.text_input("输入用户名")
    password = st.text_input("输入密码", type="password")

    # Submit button
    submit = st.form_submit_button("链接数据库")

if submit:
    if not username or not password:
        st.error("必须输入所有的数据")
        st.stop()
    else:
        st.success("链接成功")

if st.session_state['cursor'] == '':
    st.stop()

# Define the connection parameters
server = '192.168.0.253'
database = 'zhanghm_all'
driver = '{SQL Server}'

# Create a connection string
connection_string = f'DRIVER={driver};SERVER={server};DATABASE={database};UID={username};PWD={password}'

@st.cache_resource
def connect():
    connection = pyodbc.connect(connection_string)
    cursor = connection.cursor()
    return cursor

@st.cache_data
def convert_df(df):
    return df.to_excel(index=False).encode('utf-8')

# Establish a connection to the database
try:
    st.session_state['cursor'] = connect()
    
    # Execute a simple query to test the connection
    st.session_state['cursor'].execute("SELECT @@version;") 
    row = st.session_state['cursor'].fetchone()
    print(f"SQL Server version: {row[0]}")

    st.session_state['cursor'].execute('USE zhanghm_all')

except Exception as e:
    print(f"Error connecting to SQL Server: {e}")

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
    st.session_state['name'] = st.selectbox('输入需要查询的品名', result_list)

    # Submit button
    submit_button_main = st.form_submit_button("提交")

if len(st.session_state['name']) == 1:
    st.stop()

if submit_button_main:
    query = f'''
        SELECT n_vy
        FROM ggd
        WHERE c_cpbh = '{st.session_state['name']}'
    '''

    st.session_state['cursor'].execute(query)
    vy = st.session_state['cursor'].fetchone()
    vy = vy[0]

    if vy is None:
        st.warning('某些品名未找到序号，请检查输入')
        st.stop()

    Tquery = f'''
        SELECT MIN(gd.c_cpbh) AS 品种, g.c_lb AS 经纬, SUM(n_dl) AS 经重, SUM(n_dl1) AS 纬重, y.c_guige AS 规格, MIN(gd.n_nf_c) AS 门幅, MIN(gd.n_mm_c) AS 姆米, MIN(gd.n_wm_p) AS 纬密
        FROM g_ggsx g
        LEFT JOIN yclk y
            ON g.c_zhno = y.c_clbh
        LEFT JOIN ggd gd
            ON gd.n_vy = g.n_vy
        WHERE g.n_vy = {vy}
        GROUP BY g.c_lb, y.c_guige
    '''

    st.session_state['cursor'].execute(Tquery)
    rows = st.session_state['cursor'].fetchall()
    columns = [column[0] for column in st.session_state['cursor'].description]
    maindf = pd.DataFrame.from_records(rows, columns=columns)
    maindf['米用量(g)'] = maindf.apply(lambda row: row['经重'] if row['经纬'] == '经' else row['纬重'], axis=1)
    maindf['米用量(g)'] = maindf['米用量(g)'].astype(float)

    st.session_state['infos'] = []
    st.session_state['infos'].append(maindf['品种'][0])
    st.session_state['infos'].append(maindf['门幅'][0])
    st.session_state['infos'].append(maindf['姆米'][0])
    st.session_state['infos'].append(maindf['纬密'][0])

    st.session_state['maindf'] = maindf.drop(columns=['品种', '门幅', '姆米', '纬密', '经重', '纬重'])

st.write(f"品种： {st.session_state['infos'][0]}")
st.write(f"门幅： {st.session_state['infos'][1]}")
st.write(f"姆米： {st.session_state['infos'][2]}")
st.write(f"纬密： {st.session_state['infos'][3]}")
st.dataframe(st.session_state['maindf'])

with st.form("input_form"):
    prices = []

    for index, row in st.session_state['maindf'].iterrows():
        price = st.number_input(f"请根据规格输入价格：{row['经纬']}, {row['规格']} 每千克", key=index)
        prices.append(price)

    st.session_state['gf'] = st.number_input('请输入工费:')

    # Submit button for the form
    submit_button_price = st.form_submit_button("提交")

if submit_button_price:
    # Add the user inputs to a new column in the DataFrame
    st.session_state['maindf']['单价(万元每吨)'] = prices
    st.session_state['maindf']['成本'] = st.session_state['maindf']['米用量(g)'] * st.session_state['maindf']['单价(万元每吨)']  * 0.01

    hejiyuancailiao = sum(st.session_state['maindf']['成本'])
    baojia = hejiyuancailiao + st.session_state['gf']

    # Display the updated DataFrame
    st.write(st.session_state['maindf'])
    st.write(f'合计原材料成本价： {hejiyuancailiao}')
    st.write(f'工费： {st.session_state["gf"]}')
    st.header(f"报价为 {round(baojia, 2)}")

    # Function to convert DataFrame to Excel
    def to_excel(df):
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Sheet1')
        processed_data = output.getvalue()
        return processed_data

    excel_data = to_excel(st.session_state['maindf'])

    st.download_button(
        label="导出为Excel",
        data=excel_data,
        file_name='原材料.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )