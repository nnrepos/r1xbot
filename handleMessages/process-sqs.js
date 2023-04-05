require("dotenv").config();
const { Consumer } = require("sqs-consumer");
const { SQSClient } = require("@aws-sdk/client-sqs");
const { handler } = require("./index");

const ctx = { msgCount: 0 };

const app = Consumer.create({
  queueUrl: process.env.SQS_QUEUE_URL,
  handleMessage: async (message) => {
    currMsgCount = ++ctx.msgCount;
    console.log(`[${ctx}] `, "Starting to handle message");

    const result = await handler(currMsgCount, message.Body);
    console.log(`[${ctx}] `, "Finished handling message");
  },
  sqs: new SQSClient({
    region: "eu-central-1"
  })
});

app.on("error", (err) => {
  console.error(err.message);
});

app.on("processing_error", (err) => {
  console.error(err.message);
});

app.on("timeout_error", (err) => {
  console.error(err.message);
});

app.start();
