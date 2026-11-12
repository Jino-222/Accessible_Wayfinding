NAVER LABS Large-scale Localization Datasets in Crowded Indoor Spaces
*********************************************************************

We introduce five new localization datasets acquired in challenging real-world indoor environments. The datasets were captured in a large shopping mall and a large metro station in Seoul, South Korea and include images and depth maps obtained from a dedicated mapping platform comprising ten cameras and two 3D laser scanners. Compared to existing indoor datasets, the proposed datasets provide dense image sampling and cover many challenges of indoor visual localization. In addition, the datasets consist of sequences captures with time intervals of up to 128 days, thus, the datasets contain various changes over time. 

Details about the datasets
**************************

Since estimating precise ground truth camera poses for such large indoor spaces using SFM was not possible so far, we developed a novel, automated pipeline that utilizes both, LiDAR SLAM and SFM algorithms to solve this problem. The proposed pipeline applies LiDAR-based pose-graph SLAM to estimate the trajectories of our dedicated mapping platform.
Furthermore, the mapping platform is equipped with two different types of cameras; 6 industrial cameras (Basler acA2500-20gc) and 4 smartphone (Galaxy S9) cameras. The six industrial cameras are mounted at intervals of 60 degrees. They have a horizontal field of view (FoV) of more than 70 degrees, thus, a set of images can horizontally cover 360 degrees. Each camera is facing 10 degrees upwards in order to capture not too much ground surface. The four smartphones are mounted slightly above the industrial cameras to better reflect real-world applications where the capture device at test time will be different from the mapping platform. The platform and the sensors are synchronized using a network time protocol (NTP) server. Note that illumination can change easily with camera movement in indoor spaces, thus, we set the exposure time to automatic for all cameras. Please find more details in our paper.

Train, test, validation splits
******************************

Our datasets consist of database images for training and query images for testing. In addition, we split the query images into test and validation sets that represent different areas with little overlap (see paper). The ground truth poses of the validation set are released publicly, the poses of the test set are retained to build a visual localization benchmark.

Data format (kapture)
*********************

The datasets consist of the mentioned camera images, camera parameters, and poses.
Furthermore, for the mapping splits we provide LIDAR-based, sparse depth maps.

To facilitate the use of our datasets, they are provided in the kapture format (https://github.com/naver/kapture). The kapture toolbox (https://github.com/naver/kapture-localization) allows easy execution of modern visual localization methods and it enables to convert the datasets into other formats such as OpenMVG and COLMAP.

Reference
*********

If you use our dataset in research, please cite to following paper.

@inproceedings{nl_datasets,
      title={Large-scale Localization Datasets in Crowded Indoor Spaces},
      author={Donghwan Lee, Soohyun Ryu, Suyong Yeon, Yonghan Lee, Deokhwa Kim, Cheolho Han, Yohann Cabon, Philippe Weinzaepfel, Nicolas Guérin, Gabriela Csurka, and Martin Humenberger},
      year={2021},
      booktitle={IEEE Conference on Computer Vision and Pattern Recognition}
}