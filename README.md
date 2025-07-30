# System to automatically build EC2 from CSV files

## Overview

This system automatically builds an EC2 server on AWS just by uploading a CSV file describing the server specifications to a specific location.

It is a non-engineer-friendly configuration that allows you to build a server just by preparing a CSV file with a familiar spreadsheet software, even without specialized knowledge.

## Architecture Diagram

The overall picture of this system is as follows.

<p align="center">
  <img src="./images/architecture.png" alt="Architecture Diagram" width="80%">
</p>

## Processing Flow

1. **CSV Upload** 📂
   Upload the CSV file from the user's PC to S3 (file storage location).
   The user only needs to edit the csv file and hit the bat.

2. **Lambda Startup** ⚡
   Lambda (a small program) is automatically started by detecting the file upload.

3. **Parameter Reading** 📝
   Lambda reads the contents of the CSV file (server name, OS type, etc.).

4. **Instruct CloudFormation** 🗣️
   Based on the information read, it instructs CloudFormation (a service that creates infrastructure from blueprints) to "create a server like this."

5. **EC2 Server Construction** 🖥️
   CloudFormation builds the EC2 server as instructed.

## Main Features

* **Serverless**: No management server is required to run the automation.
* **Fully automated**: Once the file is uploaded, the server is completed without any further action.
* **Cost-effective**: Processing only runs when a file is uploaded, so there are no wasted costs.
* **Easy to configure**: Server specifications can be managed in the familiar CSV format.