import streamlit as st
from PIL import Image
import io
import numpy as np
import matplotlib.image as img
import os
from sklearn.cluster import KMeans

os.environ['OMP_NUM_THREADS'] = '1'

def process(img_arr, n_clusters):
    (h,w,c) = img_arr.shape
    img2D = img_arr.reshape(h*w,c)
    kmeans_model = KMeans(n_clusters=n_clusters)
    cluster_labels = kmeans_model.fit_predict(img2D)
    rgb_cols = kmeans_model.cluster_centers_
    img_quant = np.reshape(rgb_cols[cluster_labels],(h,w,c))
    return img_quant

# Page Configuration
st.set_page_config(
    page_title="矢量图",
    page_icon="🎨",
    layout="centered"
)

# Header Section
st.title("矢量图")
st.markdown("把图片颜色减少，并变为矢量图")

# File Uploader and Input Section
uploaded_file = st.file_uploader("上传图片", type=["png", "jpg", "jpeg"])
n_clusters = st.number_input("确定矢量图的颜色数量：", min_value=2, step=1)

# Process and display the image
if st.button("处理") and uploaded_file and n_clusters:
    try:
        # Open the uploaded image
        image = Image.open(uploaded_file)
        
        # Convert image to RGB if it has an alpha channel
        if image.mode == 'RGBA' or image.mode == 'LA':
            image = image.convert('RGB')

        image_array = np.array(image) / 255.0 

        # Process the image
        quantized_image = process(image_array, n_clusters)

        # Convert processed image back to PIL for display and download
        quantized_pil = Image.fromarray((quantized_image * 255).astype(np.uint8))

        # Display the quantized image
        st.image(quantized_pil, caption=f"{n_clusters}色图片", use_column_width=True)

        # Create a download button
        buffer = io.BytesIO()
        quantized_pil.save(buffer, format="BMP")
        buffer.seek(0)

        st.download_button(
            label="保存",
            data=buffer,
            file_name="矢量图.bmp",
            mime="image/bmp"
        )

    except Exception as e:
        st.error(f"An error occurred: {e}")
